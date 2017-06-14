#-*-coding:utf-8 -*-
import serial
import time,datetime
import binascii,binhex
import struct
import threading
import os
import socket,json,configparser
from apscheduler.schedulers.blocking import BlockingScheduler
global serial1,serial2,sched
global ToAnalyerSerial,HasSelected,flag,logFilePath,bRCTestMap,bRCTestCode,today,countm,countt,bResponse,SendBuffer,SendBufferID,inifile,bOS
global STX,ETX,recvserverip,recvserverport,instrumentna,SchedulerTime_SerialCommunite,SchedulerTime_SendReagentToDB,SchedulerTime_SyncReagent,SchedulerTime_KeepAlive

#接收数据服务器IP
inifile = "XPReagentSync.ini"

#recvserverip = "192.168.1.253"
#recvserverport = 11111
#instrumentna = "CentaurXP_1"

#判断os类型，true为Linux，false为windows
bOS = True;

#-------------判断是否已经确认哪个com口连接analyer------------#
HasSelected = False
#-------------判断是否已经接收到TestMap消息-------------------#
bRCTestMap=True
#-------------判断是否已经接收到ReagentInfo消息---------------#
bRCTestCode=True
#--------------用于记录Testmap接收检测尝试次数--------------------#
countm=0
#--------------用于记录reagentinfo接收尝试次数--------------------#
countt=0
#--------------如果是true，则不连接canbus，单机运行，如为false，则连接canbus运行----#
bResponse=True
#--------------试剂信息发送至数据库使用的buffer-------------------#
SendBuffer = []
SendBufferID = []

def CreateInI():
    global logFilePath, bResponse, recvserverip, recvserverport, instrumentna, SchedulerTime_SerialCommunite, SchedulerTime_SendReagentToDB, SchedulerTime_SyncReagent, SchedulerTime_KeepAlive, bOS,inifile
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
    conf.set('SchedulerT', 'SerialComm','0.1')
    conf.set('SchedulerT', 'SendReagentToDB', '1')
    conf.set('SchedulerT', 'SyncReagent', '300')
    conf.set('SchedulerT', 'KeepAlive', '60')
    conf.write(open(inifile,"w"))
    return

def LoadConfig():
    global logFilePath,bResponse,recvserverip,recvserverport,instrumentna,SchedulerTime_SerialCommunite,SchedulerTime_SendReagentToDB,SchedulerTime_SyncReagent,SchedulerTime_KeepAlive,bOS,os,inifile
    if os.path.exists(inifile) == False:
        CreateInI()
    conf = configparser.ConfigParser()
    conf.read_file(open(inifile))
    recvserverip  = conf.get('DB','ServerIP')
    recvserverport = conf.get('DB','ServerPort')
    instrumentna = conf.get('MAIN','InstrumentName')
    response = conf.get('MAIN','NeedResponse')
    if response == 'True':
        bResponse = True
    else:
        bResponse = False
    osv = conf.get('MAIN', 'OS')
    if osv == 'True':
        bOS = True
    else:
        bOS = False
    SchedulerTime_SerialCommunite = float(conf.get('SchedulerT','SerialComm'))
    SchedulerTime_SendReagentToDB = float(conf.get('SchedulerT', 'SendReagentToDB'))
    SchedulerTime_SyncReagent = float(conf.get('SchedulerT', 'SyncReagent'))
    SchedulerTime_KeepAlive = float(conf.get('SchedulerT', 'KeepAlive'))



def InitSerialPort():
    global serial1,serial2,bOS
    if bOS:
        # -----------------用于rasperry----------------------#
        serial1 = serial.Serial('/dev/ttyUSB0', 9600, 8, 'N', 1, timeout=0.5)
        if bResponse == False:
            serial2 = serial.Serial('/dev/ttyUSB1', 9600, 8, 'N', 1, timeout=0.5)
    else:
        # ------------------用于windows---------------------#
        serial1 = serial.Serial('COM2', 9600, 8, 'N', 1, timeout=0.5)
        if bResponse == False:
            serial2 = serial.Serial('COM3', 9600, 8, 'N', 1, timeout=0.5)

#------------
def printmessage(serialporttext , text):
    e=serialporttext + '   ' + time.strftime("'%Y-%m-%d %X'", time.localtime()) + ":" + text.decode('unicode-escape')
    print(e)
    writelog(e)
    hex1 = str(binascii.b2a_hex(text))[2:]
    disp1=''
    while len(hex1)>0:
        disp1 += hex1[:2] + " "
        hex1=hex1[2:]
    print(disp1)
    writelog('HEX:' + disp1)

def writelog(text):
    global today,logFilePath
    try:
        if today != datetime.date.today():
            logFilePath = "//PythonTools//SerialPort//" + time.strftime("%Y%m%d", time.localtime()) + "//"
            today = datetime.date.today()
            if os.path.exists(logFilePath) == False:
                os.mkdir(logFilePath)
        f = open(logFilePath + 'serial.log', 'a')
        f.write('\n' + text)
        f.close()
        fw = open(logFilePath + 'serial_win.log', 'a')
        fw.write('\r\n' + text)
        fw.close()
    except Exception as e:
        print(str(e))
        return


#----------串口通讯转发任务-----------

def SerialRecieveReplyThreadByAPScheduler():
    global serial1,serial2,bResponse
    print('SerialRecieveReplyThreadByAPScheduler')
    if  bResponse == False:
        text = SerialWork(serial1,serial2)
        text = text + SerialWork(serial2,serial1)
    else:
        text = SerialWork(serial1, serial1)
    Serial_Decode(text)

#--------------串口通讯处理--------------
def SerialWork(serialna_alias,serialna_other):
    global HasSelected, ToAnalyerSerial, flag, bRCTestMap, bRCTestCode, countm, countt, bResponse, bReadFinish
    try:
        l=serialna_alias.read_all()

    except Exception as e:
        print('Recieve Error:' + str(e) + '\n')
        writelog('Recieve Error:' + str(e))
    if l.decode('unicode-escape')!='':

        if bResponse == False:
            #------同时连接canbus与仪器，com1口逻辑
            if HasSelected == False:
                if ISAnalyer(l):
                    ToAnalyerSerial = serialna_alias
                    HasSelected = True
                    flag = 1
                    serialna_other.write(l)
            if HasSelected == True:
                if flag==1:
                    instrna = "Analyer"
                else:
                    instrna = "CanBus"
            else:
                instrna = serialna_alias.portstr
            printmessage(instrna, l)
        else:
            #------只连接仪器----
            ToAnalyerSerial = serialna_alias
            printmessage("Analyer", l)
            #------获取需响应返回的字符----
            responsebyte = Response(l)
            if responsebyte != None:
                serial1.write(responsebyte)
                printmessage("Rasperry", responsebyte)

    return str(binascii.b2a_hex(l))


#------试剂信息检查并解码
def Serial_Decode(msg):
    global HasSelected, ToAnalyerSerial, serial1, serial2, flag, bRCTestMap, bRCTestCode, countm, countt, bResponse, bReadFinish
    s = msg.upper()
    try:
        # --------确认是否收到testmap
        s.index("BF")
        bRCTestMap = True
        countm = 0
    except:
        bRCTestMap = False
        countm = countm + 1
    try:
        # -------确认是否收到试剂信息
        s.index("B5")
        bRCTestCode = True
        # -----多条试剂同步信息分开后逐条解码
        SepReagentInfo(s)
        countt = 0
    except:
        bRCTestCode = False
        countt = countt + 1




#-----多条试剂同步信息分开后逐条解码
def SepReagentInfo(strHEX):
    tmp = strHEX.upper()
    startpos = tmp.find("F0")
    endpos = tmp.find("F8")

    while startpos >= 0:
        reagentframe = tmp[startpos:endpos + 2]
        #-----试剂信息解码
        DecodeReagentInfo(reagentframe)
        tmp = tmp[endpos + 3:]
        startpos = tmp.find("F0")
        endpos = tmp.find("F8")

def DecodeReagentInfo(ReagentFrame):
    pos1 = ReagentFrame.find("B5")
    pos2 = ReagentFrame.find("FD")
    #-----获取试剂名称
    ReagentName = binascii.a2b_hex(ReagentFrame[pos1 + 2:pos2]).decode('unicode-escape')
    ReagentFrame = ReagentFrame[pos2 + 2:]
    #-----获取试剂severity
    ReagentSeverity = ReagentFrame[0:2]
    ReagentFrame = ReagentFrame[2:]
    pos1 = ReagentFrame.find("41")
    pos2 = ReagentFrame.find("50")
    pos3 = ReagentFrame.find("56")
    #-----获取试剂区域信息，仅为批号后的一个字母，如批号传输其长度最长仅为4个字符，故限定pos小于hex(lot + severity) = 4*2 + 1*2 = 10
    pos = 0
    ReagentArea = ""
    if pos1 >= 0 and pos1 < 10:
        pos = pos1
        ReagentArea = "Ancillary"
    else:
         if pos2 >= 0 and pos2 < 10 :
             pos = pos2
             ReagentArea = "Primary"
         else:
             if pos3>= 0 and pos3 < 10 :
                 pos = pos3
                 ReagentArea = "Vial"

    #------获取试剂批号，如果存在
    ReagentLot = binascii.a2b_hex(ReagentFrame[:pos]).decode('unicode-escape')
    ReagentFrame = ReagentFrame[pos + 2:]
    #------获取试剂数量-----------------
    ReagentCount = binascii.a2b_hex(ReagentFrame[:ReagentFrame.find("3B")]).decode('unicode-escape')
    #------获取试剂ID，未考虑多试剂的情况
    ReagentID = binascii.a2b_hex(ReagentFrame[ReagentFrame.find("3B") + 2:ReagentFrame.find("FD")]).decode('unicode-escape')


    #---------组装所有试剂信息----------------
    ReagentCountDIC = {ReagentLot:ReagentCount}
    ReagentInfo = {'id':ReagentID + ReagentName,'name':ReagentName,'ReagentType':ReagentArea,'QuantityType':1,'Severity':int(ReagentSeverity),'TestCount':int(ReagentCount),'Enabled': 1, 'Reason': 0, 'LotCount': 1,'Reagent':ReagentCountDIC}
    #ReagentSumDic = {ReagentID:ReagentInfo}
    #单条试剂信息加入传输buffer
    SendBufferID.append(ReagentID + ReagentName)
    SendBuffer.append(ReagentInfo)
    #print(ReagentName + ":" + ReagentSeverity + ":" + ReagentArea + ":" + ReagentLot + ":" + ReagentCount)
#---------建立tcp连接
def tcpconnect(ip,port):
    serverip = ip
    port = port
    sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    server_address = (serverip, port)
    sock.connect(server_address)
    return sock

#---------发送试剂信息到数据库更新程序任务
def SendReagentInfoToDbByAPScheduler():
    global SendBuffer,SendBufferID
    print('SendReagentInfoToDbByAPScheduler')
    NeedSend = False
    SendDic = {}
    try:
        if len(SendBuffer) > 0 :
            sendres = tcpconnect(recvserverip, recvserverport)
            while len(SendBuffer) > 0 :
                text = SendBuffer.pop(0)
                id = SendBufferID.pop(0)
                SendDic[id] = text
                NeedSend = True
            if NeedSend == True:
                sendres.send(str.encode(instrumentna + "|testmap|" + json.dumps(SendDic)))
                printlog("Send to Server: " + str(SendDic))
            sendres.close()
    except Exception as e:
        printlog("Send Msg FAIL:" + str(e))
        pass


def printlog(text):  #同步显示及记录日志文件
    try:
        os.mkdir(logFilePath)
    except:
        pass
    print (text)

    f = open(logFilePath + 'serial.log', 'a')
    f.write('\n' + text)
    f.close()
    fw = open(logFilePath + 'serial_win.log', 'a')
    fw.write('\r\n' + text)
    fw.close()

#------------------------------------

def ISAnalyer(text):

    s =  str(binascii.b2a_hex(text))
    s = s.upper()

    strCheckArray = []
    strCheckArray.append('F001AE014230F8')
    strCheckArray.append('F001C04331')
    
    for strc in strCheckArray:
        if s.find(strc) >= 0 :
            return True
    return False
    
def Response(text):
    k = str(binascii.b2a_hex(text)).upper()
    strP = k.find("F0")
    if strP >= 0 :
        if k.find("BF") >= 0:
            returnstr = "06BFF001E9014542F8"
            return binascii.a2b_hex(returnstr)
        if k.find("B5") >= 0:
            returnstr = "06B5F001AF014231F8"
            return binascii.a2b_hex(returnstr)

        returnstr = "06" + k[strP + 4:strP + 6]
        return binascii.a2b_hex(returnstr)
    else:
        return None

def KeepAlive():
    KeepAliveBytes =  binascii.a2b_hex("F001803831F8")
    serial1.write(KeepAliveBytes)



def TimerSendReagentRequestByAPScheduler():
    global HasSelected, ToAnalyerSerial, bRCTestMap, countm, countt
    print('TimerSendReagentRequestByAPScheduler')
    if HasSelected == True:

        writelog(ToAnalyerSerial.portstr + ' IS To Analyer')
        s = binascii.a2b_hex('F001B44235F8')
        if bRCTestMap or countm > 5:
            try:
               ToAnalyerSerial.write(s)
               bRCTestMap = False
               print('Rasperry To Analyer :' + 'Send F001B44235F8' + '\n')
               writelog('Rasperry Send To Analyer : F001B44235F8')
            except:
                print('Rasperry To Analyer :' + 'Send Error' + '\n')
                writelog('Rasperry Send To Analyer : Error')
            countm = 0
        else:
            print('Has not Recieved test map' + + '\n')
            writelog('Has not Recieved test map')
        time.sleep(20)
        writelog(ToAnalyerSerial.portstr + ' IS To Analyer')
        s = binascii.a2b_hex('F001B34234F8')
        if bRCTestCode or countt > 5:
            try:
                ToAnalyerSerial.write(s)
                print('Rasperry To Analyer :' + 'Send F001B34234F8' + '\n')
                writelog('Rasperry Send To Analyer : F001B34234F8')
            except:
                print('Rasperry To Analyer :' + 'Send Error' + '\n')
                writelog('Rasperry Send To Analyer : Error')
            countt = 0
        else:
            print('Has not Recieved Reagent Count' + '\n')
            writelog('Has not Recieved Reagent Count')


def MakeSche():
    global sched
    while True:
        print('makesche' + str(SchedulerTime_SerialCommunite) + str(SchedulerTime_SyncReagent) + str(SchedulerTime_SendReagentToDB))
        sched = BlockingScheduler()
        sched.add_job(SerialRecieveReplyThreadByAPScheduler, 'interval', seconds=SchedulerTime_SerialCommunite,
                  id='SerialRecieveReplyThreadByAPScheduler')
        sched.add_job(TimerSendReagentRequestByAPScheduler, 'interval', seconds=SchedulerTime_SyncReagent,
                  id='TimerSendReagentRequestByAPScheduler')
        sched.add_job(SendReagentInfoToDbByAPScheduler, 'interval', seconds=SchedulerTime_SendReagentToDB,
                  id='SendReagentInfoToDbByAPScheduler')

        if bResponse:
            sched.add_job(KeepAlive, 'interval', seconds=SchedulerTime_KeepAlive, id='KeepAlive')

        sched.start()
        time.sleep(0.3)

def SyncSetting():
    global sched,inifile
    while True:
        time.sleep(10)
        conf = configparser.ConfigParser()
        conf.read_file(open(inifile))
        asyncseting = conf.get('MAIN', 'Asyncflag')
        if asyncseting != "0":
            conf.set('MAIN', 'Asyncflag','0')
            conf.write(open(inifile, "w"))
            LoadConfig()
            sched.shutdown(True)

        time.sleep(60)



if __name__ == '__main__':
    global logFilePath,SchedulerTime_SerialCommunite,SchedulerTime_SendReagentToDB,SchedulerTime_SyncReagent,SchedulerTime_KeepAlive
    logFilePath = "//PythonTools//SerialPort//" + time.strftime("%Y%m%d",time.localtime()) + "//"
    LoadConfig()
    InitSerialPort()
    today = datetime.date.today()


    try:
        if os.path.exists(logFilePath) == False:
            os.mkdir(logFilePath)
    except:
        logFilePath = ""
    threads = []
    SerialT = threading.Thread(target=MakeSche)
    threads.append(SerialT)
    SendT = threading.Thread(target=SyncSetting)
    threads.append(SendT)
    for t in threads:
        t.setDaemon(True)
        t.start()
        time.sleep(1)
    t.join()



    #sched = BlockingScheduler()
    #sched.add_job(SerialRecieveReplyThreadByAPScheduler, 'interval', seconds=SchedulerTime_SerialCommunite,id='SerialRecieveReplyThreadByAPScheduler')
    #sched.add_job(TimerSendReagentRequestByAPScheduler, 'interval', seconds=SchedulerTime_SyncReagent,id='TimerSendReagentRequestByAPScheduler')
    #sched.add_job(SendReagentInfoToDbByAPScheduler, 'interval', seconds=SchedulerTime_SendReagentToDB,id='SendReagentInfoToDbByAPScheduler')

    #if bResponse:
    #    sched.add_job(KeepAlive, 'interval', seconds=SchedulerTime_KeepAlive,id='KeepAlive')


    #sched.start()
    #print("1234567890")

    #while True:
    #   l=serial1.read_all()
    #   if l.decode('unicode-escape')!='':
    #       serial2.write(l)
    #       printmessage(serial1.portstr,l)
    #   time.sleep(0.2)
    #   p = serial2.read_all()
    #   if p.decode('unicode-escape')!='':
    #       serial1.write(p)
    #       printmessage(serial2.portstr,p)
    #   time.sleep(0.2)



        
