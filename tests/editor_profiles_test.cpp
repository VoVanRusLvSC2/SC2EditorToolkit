#include "../src/editor_compatibility.h"
#include <iostream>
#include <cstdlib>
static void Check(bool value){if(!value){std::cerr<<"Editor profile isolation failed\n";std::exit(1);}}
int main(){
    const EditorBuildProfile* old=nullptr;const EditorBuildProfile* current=nullptr;
    for(auto& profile:kEditorBuildProfiles){if(std::string(profile.version)=="5.0.17.98310")old=&profile;if(std::string(profile.version)=="5.0.17.98745")current=&profile;}
    Check(old&&current);Check(FindEditorBuildProfile(old->sha256)==old&&old->nativeOffsets);
    Check(FindEditorBuildProfile(current->sha256)==current&&!current->nativeOffsets);
    Check(!FindEditorBuildProfile(std::string(64,'0')));
    Check(!CurrentEditorHasVerifiedOffsets());
    std::cout<<"Editor exact fingerprints, separate portable/offset profiles and unknown-image refusal passed\n";
}
