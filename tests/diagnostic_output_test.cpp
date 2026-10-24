#include "../src/diagnostic_output.h"
#include <iostream>
#include <cstdlib>
static void Check(bool value){if(!value){std::cerr<<"Diagnostic output identity regression\n";std::exit(1);}}
int main(){
    for(auto title:{L"Console - StarCraft II Editor",L"Консоль - StarCraft II Editor"}){
        Check(DiagnosticOutputId(title)==15);Check(DiagnosticOutputId(title)!=13);
    }
    for(auto title:{L"Messages - StarCraft II Editor",L"Сообщения - StarCraft II Editor"})Check(DiagnosticOutputId(title)==13);
    for(auto title:{L"Console input",L"Script Test - StarCraft II Editor",L"Messages",L""})Check(DiagnosticOutputId(title)==-1);
    std::cout<<"Diagnostic output: Console output 15, input 13 excluded; Messages output 13 passed\n";
}
