"""Opt-in native full-map/filter acceptance on a private make_terrain_fixture map.

Compare disabled categories against an independent native export of a private
copy with placements removed. No input injection or desktop switches.
"""
import argparse,concurrent.futures,json,math,shutil,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image,ImageChops,ImageStat
from live_parallel_workers import ROOT,Server as BaseServer,existing_editors,process_time,sha


class Server(BaseServer):
    def good(self,route,body=None):
        code,result=self.call(route,body);assert code==200 and result.get('status')!='FAILED',result.get('error')
        observed=result.get('desktopObservation')
        if observed:
            assert observed['visibleWindowsOnUserDesktopPeak']==observed['editorForegroundSamples']==0
            assert not observed['inputInjectionUsed'] and not observed['desktopSwitchApiUsed']
            # A person can lock/unlock Windows during an offline export. Keep
            # that observation without claiming the toolkit switched desktops.
        return result


def reference_map(source,work):
    tool=ROOT/'tools/mpqcli/mpqcli.exe'
    objects=ET.fromstring(subprocess.check_output([str(tool),'read','Objects',str(source)],creationflags=subprocess.CREATE_NO_WINDOW))
    placements=[dict(n.attrib,kind=n.tag) for n in objects if n.tag in ('ObjectUnit','ObjectDoodad')]
    for node in list(objects):
        if node.tag in ('ObjectUnit','ObjectDoodad'):objects.remove(node)
    component=work/'ReferenceObjects.xml';component.write_bytes(ET.tostring(objects,encoding='utf-8',xml_declaration=True))
    target=work/'Reference.SC2Map';shutil.copyfile(source,target)
    subprocess.run([str(tool),'add','-w','-p','Objects',str(target),str(component)],check=True,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
    return target,placements


def semantic_checks(images,placements,dimensions):
    reference=images['Reference'];observations=[]
    # Southern buildings are outside Hatchery creep. Creep is a native terrain
    # effect and legitimately remains when unit models are hidden.
    chosen=[p for p in placements if p.get('UnitType') in ('CommandCenter','Nexus') or p['kind']=='ObjectDoodad']
    assert len(chosen)>=6
    for p in chosen:
        unit=p['kind']=='ObjectUnit';x,y,_=map(float,p['Position'].split(','));radius=4 if unit else 2.5;w,h=reference.size
        box=(max(0,math.floor((x-radius)*w/dimensions[0])),max(0,math.floor((dimensions[1]-y-radius)*h/dimensions[1])),
             min(w,math.ceil((x+radius)*w/dimensions[0])),min(h,math.ceil((dimensions[1]-y+radius)*h/dimensions[1])))
        target=reference.crop(box)
        errors={name:sum(ImageStat.Stat(ImageChops.difference(im.crop(box),target)).mean)/3 for name,im in images.items() if name!='Reference'}
        present=('All','UnitsOnly','Restored') if unit else ('All','NoUnits','Restored')
        absent=('NoUnits','Ground') if unit else ('UnitsOnly','Ground')
        assert min(errors[n] for n in present)>=1,(p,'missing enabled model',errors)
        tolerance=max(.5,min(errors[n] for n in present)*.05)
        assert max(errors[n] for n in absent)<=tolerance,(p,'disabled model remains',errors)
        observations.append({'id':p['Id'],'type':p.get('UnitType') or p.get('Type'),'kind':'unit' if unit else 'doodad',
                             'referenceMeanAbsoluteRgbError':errors,'disabledTolerance':tolerance})
    return observations


def presence_checks(image,reference,placements,dimensions):
    """High-resolution geometry must differ from the independent empty map."""
    assert image.size==reference.size;observations=[];w,h=image.size
    for p in placements:
        if p.get('UnitType') not in ('CommandCenter','Nexus') and p['kind']!='ObjectDoodad':continue
        x,y,_=map(float,p['Position'].split(','));radius=4 if p['kind']=='ObjectUnit' else 2.5
        box=(max(0,math.floor((x-radius)*w/dimensions[0])),max(0,math.floor((dimensions[1]-y-radius)*h/dimensions[1])),
             min(w,math.ceil((x+radius)*w/dimensions[0])),min(h,math.ceil((dimensions[1]-y+radius)*h/dimensions[1])))
        error=sum(ImageStat.Stat(ImageChops.difference(image.crop(box),reference.crop(box))).mean)/3
        assert error>=1,(p,'high-resolution model missing',error)
        observations.append({'id':p['Id'],'meanAbsoluteRgbErrorAgainstEmptyMap':error})
    assert len(observations)>=6
    return observations


def search_checks(server,source,fixture):
    common={'map':str(source)};result=server.good('/objects/search',{**common,'kinds':['unit'],'limit':5})
    assert result['totalMatches']==fixture['units'] and not result['editorRequired'];seen=[]
    while True:
        seen += [p['objectKey'] for p in result['objects']]
        if result['nextOffset'] is None:break
        result=server.good('/objects/search',{**common,'kinds':['unit'],'limit':5,'offset':result['nextOffset']})
    assert len(seen)==len(set(seen))==fixture['units']
    assert server.good('/objects/search',{**common,'kinds':['doodad']})['totalMatches']==fixture['doodads']
    assert server.good('/objects/search',{**common,'kinds':['unit'],'owner':2})['totalMatches']==0
    result=server.good('/objects/search',{**common,'query':'commandCENTER','owner':1,'kinds':['unit']});assert result['totalMatches']==1
    position=result['objects'][0]['position']
    bounds={'left':position['x']-4,'right':position['x']+4,'bottom':position['y']-4,'top':position['y']+4}
    result=server.good('/objects/search',{**common,'bounds':bounds,'kinds':['unit']})
    assert result['totalMatches']==1 and result['objects'][0]['type']=='CommandCenter'
    return bounds


def export(server,name,source,work,size,units=True,doodads=True):
    request={'size':size,'include_units':units,'include_doodads':doodads,'output':str(work/(name+'.png'))}
    if source is not None:request['map']=str(source)
    result=server.good('/terrain/export',request)
    assert result['status']=='MAP_IMAGE_EXPORTED' and result['wholeMapVerified']
    assert result['objectFiltersVerified'] and result['sourceUnchanged'] and not result['desktopScreenshot']
    settings=result['native']['terrainExport']
    assert all(settings[k] for k in ('fullMap','topDown','optionsConfirmed','filtersConfirmed','customOptions','exported'))
    assert bool(settings['actualUnits'])==units and bool(settings['actualDoodads'])==doodads
    state=json.loads((server.runtime/'worker.json').read_text());server.state=state;server.created=state['createTimeFiletime']
    server.editor_pin=(Path(state['editorPath']),state['editorInfo']['sha256'])
    with Image.open(request['output']) as image:pixels=image.convert('RGB')
    assert pixels.width==size
    natives=[p for p in (server.runtime/'map-images').rglob('*.tga') if sha(p)==result['nativeImageSha256']];assert len(natives)==1
    with Image.open(natives[0]) as native:assert native.convert('RGB').tobytes()==pixels.tobytes()
    assert server.download(result['artifact'])==Path(request['output']).read_bytes()
    return pixels,result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--map',required=True);parser.add_argument('--work',required=True)
    parser.add_argument('--package',action='store_true');parser.add_argument('--size',type=int,default=1024,choices=(512,1024,2048,4096))
    parser.add_argument('--parallel',action='store_true');parser.add_argument('--all-sizes',action='store_true');args=parser.parse_args()
    source=Path(args.map).resolve(strict=True);fixture=json.loads(source.with_suffix('.fixture.json').read_text())
    assert fixture['units']>=4 and fixture['doodads']>=1;digest=sha(source)
    work=Path(args.work).resolve();work.mkdir(parents=True,exist_ok=False);reference,placements=reference_map(source,work)
    baseline=existing_editors();servers=[];report={'status':'FAILED','scope':'Private fixture, supported Editor and tested device only'}
    try:
        server=Server('Map',work/'main',args.package);servers.append(server);bounds=search_checks(server,source,fixture);images={};extra=None
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            if args.parallel:
                other=Server('Independent',work/'independent',args.package);servers.append(other)
                extra=executor.submit(export,other,'IndependentGround',source,work,args.size,False,False)
            results=[]
            for index,(name,units,doodads) in enumerate([('All',True,True),('NoUnits',False,True),('Ground',False,False),('UnitsOnly',True,False),('Restored',True,True)]):
                print('Native export:',name,flush=True)
                images[name],result=export(server,name,source if index==0 else None,work,args.size,units,doodads);results.append(result)
                assert abs(images[name].height-round(args.size*fixture['dimensions'][1]/fixture['dimensions'][0]))<=1
            # Reuse one persistent document so a reset/re-enable bug cannot be
            # concealed by reopening the map between visibility settings.
            images['Reference'],_=export(server,'Reference',reference,work,args.size)
            observations=semantic_checks(images,placements,fixture['dimensions'])
            if extra:
                independent,other_result=extra.result()
                semantic_checks({**images,'Ground':independent},placements,fixture['dimensions'])
                assert other_result['instanceId']!=results[0]['instanceId'];report['independentFilterWorker']='PASS'
            sizes={args.size:images['Reference']}
            if args.all_sizes:
                for size in (512,1024,2048,4096):
                    if size!=args.size:sizes[size],_=export(server,'Size'+str(size),None,work,size)
        target=work/'All.png';before=sha(target);code,_=server.call('/terrain/export',{'output':str(target)})
        assert code==409 and sha(target)==before
        for invalid in ({'output':''},{'output':12},{'include_units':'false'},{'size':True}):
            code,_=server.call('/terrain/export',invalid);assert code==400
        region=server.good('/terrain/region',{'map':str(source),'size':args.size,'bounds':bounds,'output':str(work/'CornerRegion.png')})
        assert region['regionCropVerified'] and not region['region']['resampled']
        highres=None
        if args.all_sizes:
            highres_image,_=export(server,'HighResolutionObjects4096',None,work,4096)
            highres=presence_checks(highres_image,sizes[4096],placements,fixture['dimensions'])
        compiled=server.good('/triggers/compile',{});assert compiled['nativeCompilePassed'] and compiled['compilerErrors']==0
        galaxy=server.good('/galaxy/export',{});assert server.download(galaxy['artifact']).decode('utf8')==compiled['galaxy']
        diagnostics=server.good('/editor/diagnostics',{})
        assert diagnostics['editorLog']['inspected'] and diagnostics['editorLog']['complete'] and diagnostics['editorLog']['clear'] is True
        assert sha(source)==digest
        report.update(status='AUTOMATED_NATIVE_MAP_AND_FILTER_ACCEPTANCE_PASSED_VISUAL_REVIEW_REQUIRED',
            nativeFilterMatrix='PASS: four states and restoration in one persistent worker',semanticLandmarks=observations,
            allSupportedSizes=args.all_sizes,exactNativeTgaPngPixels=True,exactDownloads=True,savedObjectSearchFilters='PASS',
            highResolutionModelPresence=highres,
            nativeCompileErrors=0,sourceUnchanged=True,visualReviewRequired='Review four corner buildings, hills, doodads, disabled states and southwest crop',
            desktopObservations=[r['desktopObservation'] for r in results])
    finally:
        for server in reversed(servers):server.close()
        report['allTestApisStopped']=all(s.process.poll() is not None for s in servers)
        report['allTestEditorsClosed']=all(not s.state or process_time(s.state['pid'])!=s.created for s in servers)
        report['installedEditorUnchanged']=all(not hasattr(s,'editor_pin') or sha(s.editor_pin[0])==s.editor_pin[1] for s in servers)
        after=existing_editors();report['remainingBaselineEditors']=len([p for p,t in baseline.items() if after.get(p)==t])
        report['existingEditorsControlled']=False
        (work/'VERIFICATION.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(report['status'],flush=True);return 0


if __name__=='__main__':raise SystemExit(main())
