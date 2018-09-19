import DBConnect as db;
import SerialOnRasperry as sor;
import ReagentDecode as RD;
import binascii,binhex
import gc
def MakeReagentMap(InstrumentName,TestMapDIC):
    #sor.LoadConfig();
    #instrumentname = sor.instrumentna;
    reagentinfos = [];
    sql = "select distinct(reagent_name),reagent_type,reagent_lot from sys_info.reagent_detail where instrument_name = '" + InstrumentName + "' and  onboard = 1 order by reagent_name";
    results = db.FetchData(sql);
    testmaphexcode = "01BF";
    for row in results :
        ReagentName = str(row[0])
        if ReagentName in TestMapDIC:
            print('1');
            id = TestMapDIC[ReagentName];
            print(id);
        else :
            id = row[2];
        testmaphexcode += str_to_hex(id + ";" + ReagentName) + "FD";
        reagenttype = row[1];
        reagenttype = str(row[1]).upper()[0:1];
        reagentcount = GetReagentCount(ReagentName,InstrumentName);
        reagentinfo = "01B5" + str_to_hex(ReagentName) + "FD01" + str_to_hex(row[2] + reagenttype + reagentcount + ";" + id) + "FD";
        reagentinfo = "F0" + reagentinfo + checksum(reagentinfo) + "F8";
        reagentinfos.append(reagentinfo);
    sum = checksum(testmaphexcode)
    testmaphexcode = "F0" + testmaphexcode + sum + "F8";
    return testmaphexcode,reagentinfos;

def GetReagentCount(ReagentName,InstrumentName):
    sql = "select reagent_name,reagent_count from sys_info.reagent_detail where instrument_name = '" + InstrumentName + "' and  onboard = 1 and reagent_name = '" + ReagentName +"' order by reagent_name";
    results = db.FetchData(sql);
    count = 0;
    for r in results :
        count += int(r[1]);
    return str(count);
    

def str_to_hex(s):
    return  ' '.join([hex(ord(c)).replace('0x','') for c in s]).upper().replace(' ','')

def checksum(text):
    text = text.upper()
    sumall = 0
    for i in range(int(len(text)/2)):
        sumall = sumall + int(text[i*2:(i+1)*2],16)
    sumall = hex(sumall % 256)[2:]
    if len(sumall) == 1:  
        h = str(30)
        l = str((hex(ord(str(sumall).upper()))))[2:]
    else:
        h = str((hex(ord(str(sumall[0]).upper()))))[2:]
        l = str((hex(ord(str(sumall[1]).upper()))))[2:]
    gc.collect()
    return h+l;


if __name__ == '__main__':
    strs = "f001bf46353b54534833554cfd32353b445259fd33333b61484356fd33383b615447fd34353b5765745761736831fd34363b4842654167fd37383b465434fd38313b5434fd38363b465433fd39363b5765745761746572fd3130343b6154504ffd3130373b53595048fd3131323b5433fd3834f8 ";
    sor.LoadConfig();
    dic = sor.GetTestMap(strs.upper());
    rmap,rinfo =  MakeReagentMap(sor.instrumentna,dic);
    print(rmap);
    print(rinfo);