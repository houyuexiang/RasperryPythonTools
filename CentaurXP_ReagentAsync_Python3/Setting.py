import configparser;
import os;
global inifile;

inifile = "XPReagentSync.ini"

def CreateInI():
    global inifile
    conf = configparser.ConfigParser()
    conf.add_section('MAIN')
    conf.add_section('DB')
    conf.add_section('SchedulerT')
    conf.set('MAIN','NeedResponse','False')
    conf.set('MAIN', 'InstrumentName', 'CentaurXP_1')
    conf.set('MAIN', 'OS','True')
    conf.set('MAIN', 'asyncflag','0')
    conf.set('DB', 'ServerIP', '127.0.0.1')
    conf.set('DB', 'ServerPort', '11111')
    conf.set('DB','DBName','sys_info');
    conf.set('DB','DBHost','192.168.1.250');
    conf.set('DB','DBPort','3306');
    conf.set('DB','Username','root');
    conf.set('DB','Password','root');
    conf.set('SchedulerT', 'SerialComm','0.5')
    conf.set('SchedulerT', 'SendReagentToDB', '1')
    conf.set('SchedulerT', 'SyncReagent', '300')
    conf.set('SchedulerT', 'SyncReagentFromDB','0')
    conf.set('SchedulerT', 'KeepAlive', '60')
    conf.write(open(inifile,"w"))
    return


def GetSetting(section,key,default = ''):
    global inifile;
    if os.path.exists(inifile) == False:
        CreateInI()
    conf = configparser.ConfigParser()
    try:
        conf.read_file(open(inifile))
        var = conf.get(section,key)
    except:
        var = default
        print(default)
    return var
