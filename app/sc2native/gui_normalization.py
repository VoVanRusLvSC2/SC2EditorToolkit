"""Detect authored GUI identities discarded by original native serialization."""
import hashlib
from .map_objects import xml_root


def identities(data):
    root=xml_root(data,'TriggerData');found=set()
    for library,node in [('',root)]+[(lib.get('Id','').upper(),lib) for lib in root.findall('Library')]:
        for element in node.findall('Element'):
            key=(library,element.get('Type',''),element.get('Id','').upper())
            if not key[1] or not key[2] or key in found:raise ValueError('Missing or duplicate typed GUI identity')
            found.add(key)
    return found


def compare_native_gui(submitted,saved):
    before,after=identities(submitted),identities(saved)
    removed=sorted(before-after)
    return {'submittedSha256':hashlib.sha256(submitted).hexdigest(),'nativeSavedSha256':hashlib.sha256(saved).hexdigest(),
        'byteEqual':submitted==saved,'submittedElements':len(before),'savedElements':len(after),
        'removedElementCount':len(removed),'removedElements':[dict(zip(('library','type','id'),key)) for key in removed[:128]],
        'removedElementsTruncated':len(removed)>128,'semanticEquivalenceVerified':False}
