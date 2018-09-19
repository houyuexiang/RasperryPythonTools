import binascii,binhex
global dict;
def GetTestMap(map):
    global dic;
    dic = {};
    map = map.upper();
    startpos = map.find("BF");
    endpos = map.find("F8")
    rmap = map[startpos + 4:endpos - 4];
    fdpos = rmap.find("FD");
    while fdpos > 0 :
        spilt = rmap[0:fdpos];
        pos = spilt.find("3B");
        HEXID = spilt[0:pos];
        HEXName = spilt[pos + 2:];
        ReagentID = binascii.a2b_hex(HEXID).decode('unicode-escape');
        ReagentName = binascii.a2b_hex(HEXName).decode('unicode-escape');
        rmap = rmap[fdpos + 2:]
        dic[ReagentName] = ReagentID;
        fdpos = rmap.find("FD");
    print(dic);
    return dic;




if __name__ == '__main__':
    strs = "f001bf46353b54534833554cfd32353b445259fd33333b61484356fd33383b615447fd34353b5765745761736831fd34363b4842654167fd37383b465434fd38313b5434fd38363b465433fd39363b5765745761746572fd3130343b6154504ffd3130373b53595048fd3131323b5433fd3834f8 ";
    GetTestMap(strs.upper());
    