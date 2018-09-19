#-*-coding:utf-8 -*-
import serial
import time,datetime
import binascii,binhex
import struct
import threading
import os
import socket,json,configparser
import gc
from apscheduler.schedulers.blocking import BlockingScheduler
from Setting import *;
import DBConnect as db;
from ReagentDecode import GetTestMap;
from ReagentEncode import MakeReagentMap;
global serial1,serial2,sched,SyncReagentFromDB;
global ToAnalyerSerial,ToCanbusSerial,HasSelected,flag,logFilePath,bRCTestMap,bRCTestCode,today,countm,countt,bResponse,SendBuffer,SendBufferID,inifile,bOS
global STX,ETX,recvserverip,recvserverport,instrumentna,SchedulerTime_SerialCommunite,SchedulerTime_SendReagentToDB,SchedulerTime_SyncReagent,SchedulerTime_KeepAlive
global bInReagentAsync,bInSampleQueueCommand,ReagentAsyncArray,bSendReagent
global SerialList1,SerialList2,DICTestmap
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
ReagentAsyncArray = []
#--------------处于发送试剂信息过程中---------#
bSendReagent = False


def LoadConfig():
    global logFilePath,bResponse,recvserverip,recvserverport,instrumentna,SchedulerTime_SerialCommunite,SchedulerTime_SendReagentToDB,SchedulerTime_SyncReagent,SchedulerTime_KeepAlive,bOS,os,inifile
    global bInReagentAsync,bInSampleQueueCommand
    global SyncReagentFromDB
    recvserverip  = GetSetting('DB','ServerIP')
    recvserverport = GetSetting('DB','ServerPort')
    instrumentna = GetSetting('MAIN','InstrumentName')
    response = GetSetting('MAIN','NeedResponse')
    if response == 'True':
        bResponse = True
    else:
        bResponse = False
    osv = GetSetting('MAIN', 'OS')
    if osv == 'True':
        bOS = True
    else:
        bOS = False
    SyncReagentFromDB =  GetSetting('SchedulerT','SyncReagentFromDB')
    SchedulerTime_SerialCommunite = float(GetSetting('SchedulerT','SerialComm'))
    SchedulerTime_SendReagentToDB = float(GetSetting('SchedulerT', 'SendReagentToDB'))
    SchedulerTime_SyncReagent = float(GetSetting('SchedulerT', 'SyncReagent'))
    SchedulerTime_KeepAlive = float(GetSetting('SchedulerT', 'KeepAlive'))
    db.LoadConfig();




def InitSerialPort():
    global serial1,serial2,bOS
    if bOS:
        # -----------------用于rasperry----------------------#
        serial1 = serial.Serial('/dev/ttyUSB0', 9600, 8, 'N', 1,timeout=0.5)
        if bResponse == False:
            serial2 = serial.Serial('/dev/ttyUSB1', 9600, 8, 'N', 1,timeout=0.5)
            
    else:
        # ------------------用于windows---------------------#
        serial1 = serial.Serial('COM2', 9600, 8, 'N', 1,timeout=0.5)
        if bResponse == False:
            serial2 = serial.Serial('COM3', 9600, 8, 'N', 1,timeout=0.5)

#------------
def printmessage(serialporttext , text):
    e=serialporttext + '   ' + str(datetime.datetime.now()) + ":" + text.decode('unicode-escape')
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
            logFilePath = "//PythonTools//CentaurXPReagentAsync//" + time.strftime("%Y%m%d", time.localtime()) + "//"
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


def SerialRecieveReplyThreadByThread():
    global serial1, serial2, bResponse
    while True:
        if  bResponse == False:
            text = SerialWork(serial1,serial2)
            text = text + SerialWork(serial2,serial1)
        else:
            text = SerialWork(serial1, serial1)
        Serial_Decode(text)
        time.sleep(0.001)


def CheckRecieveAll(byte):
    tmp = str(binascii.b2a_hex(byte)).upper()
    if tmp.find('F0') >=0 and tmp.find('F8')<=0 :
        return True
    if tmp.find('06') >= 0 and tmp.find('F0') >=0 and tmp.find('F8')<0:
        return True
    if tmp.find('06') >= 0 and len(tmp) < 6:
        return True
    return False
        

#--------------串口通讯处理--------------
def SerialWork(serialna_alias,serialna_other):
    global HasSelected, ToAnalyerSerial,ToCanbusSerial, flag, bRCTestMap, bRCTestCode, countm, countt, bResponse, bReadFinish,ReagentAsyncArray,bSendReagent
    try:
        #l=serialna_alias.readall()
        l=serialna_alias.read(serialna_alias.inWaiting())

    except Exception as e:
        print('Recieve Error:' + str(e) + '\n')
        writelog('Recieve Error:' + str(e))
        return

    if l.decode('unicode-escape')!='':
        while CheckRecieveAll(l):
            l = l + serialna_alias.read(serialna_alias.inWaiting())
            time.sleep(0.01)
        
        if bResponse == False:
            #------同时连接canbus与仪器，com1口逻辑

            if HasSelected == False:
                if ISAnalyer(l):
                    ToAnalyerSerial = serialna_alias
                    ToCanbusSerial = serialna_other
                    HasSelected = True

            if HasSelected == True:
                if serialna_alias==ToAnalyerSerial:
                    instrna = "Analyer"
                else:
                    instrna = "CanBus"
            else:
                instrna = serialna_alias.portstr

            #判断是否需要转发
            if HasSelected:
                p = CheckSampleQueueCommandDuringReagentAsync(l)
            else:
                p = l
            serialna_other.write(p)
            printmessage(instrna, l)
            #如果修改传输内容，则记录
            if p!=l:
                printmessage('Raspberry edit',p)
        else:
            #------只连接仪器----
            ToAnalyerSerial = serialna_alias
            printmessage("Analyer", l)
            #------获取需响应返回的字符----
            responsebyte = Response(l)
            if responsebyte != None:
                serial1.write(responsebyte)
                printmessage("Rasperry", responsebyte)
        print('end' + str(datetime.datetime.now()))
        return str(binascii.b2a_hex(l))
    else:
        
        #闲时发送未发送的试剂信息
        if len(ReagentAsyncArray) > 0 and HasSelected and bInSampleQueueCommand == False:
            p = binascii.a2b_hex(ReagentAsyncArray.pop())
            ToCanbusSerial.write(p)
            printmessage("Rasperry Send To Canbus", p)
            bSendReagent = True
            time.sleep(0.05)
        else:
            bSendReagent = False
        return ''


def CheckSampleQueueCommandDuringReagentAsync(text):
    global ToAnalyerSerial,ToCanbusSerial,bInReagentAsync,bInSampleQueueCommand,bSendReagent
    tmp = str(binascii.b2a_hex(text)).upper()
    tmp = tmp[2:len(tmp) - 1]
    print(tmp)
    pos = tmp.find('06')
    if pos >= 0:
        message = tmp[pos:pos + 4]
        # 试剂同步结束
        #xp-->canbus
        if message.find('AF') >=0:
            bInReagentAsync = False
            #确定是rasbperry进行应答，则将消息中的06af去掉
            if bInSampleQueueCommand:
                tmp = tmp.replace(message, '')
        # samplequeuecommand结束
        # xp-->canbus
        if message.find('CF')>= 0:
            bInSampleQueueCommand = False
        # canbus -->raspberry
        if message.find('B5') >= 0 and bSendReagent:
            tmp = tmp.replace(message,'')

    startpos = tmp.find('F0')
    endpos = tmp.find('F8')
    if startpos >= 0 and endpos >= 0:
        message = tmp[startpos:endpos + 2]
        #试剂同步消息
        pos  = message.find('B5')
        if pos >= 0 :
            #收到试剂消息，如果已经收到samplequeuecommand之后，且这个命令并未完成，则直接保存试剂消息，并自动应答
            bInReagentAsync = True
            if bInSampleQueueCommand:
                ReagentAsyncArray.append(message)
                Replystr = binascii.a2b_hex('06B5F001AF014231F8')
                ToAnalyerSerial.write(Replystr)
                printmessage('Raspberry Send to Analyer:',Replystr)
                tmp = tmp.replace(message,"")
        #samplequeuecommand
        pos = message.find('A0')
        if pos >= 0 :
            bInSampleQueueCommand = True
        #raspberry --> canbus
        pos = message.find('AF')
        if pos >=0 and bSendReagent:
            Replystr = binascii.a2b_hex('06AF')
            ToCanbusSerial.write(Replystr)
            printmessage('Raspberry Send to Canbus:', Replystr)
            tmp = tmp.replace(message, "")







    return binascii.a2b_hex(tmp)


#------试剂信息检查并解码
def Serial_Decode(msg):
    global HasSelected, ToAnalyerSerial, serial1, serial2, flag, bRCTestMap, bRCTestCode, countm, countt, bResponse, bReadFinish
    global SchedulerTime_SendReagentToDB,DICTestmap
    s = msg.upper()
    try:
        # --------确认是否收到testmap
        s.index("BF")
        bRCTestMap = True
        countm = 0
        DICTestmap = GetTestMap(s);
    except:
        bRCTestMap = False
        countm = countm + 1
    try:
        # -------确认是否收到试剂信息
        s.index("B5")
        bRCTestCode = True
        # -----多条试剂同步信息分开后逐条解码
        if SchedulerTime_SendReagentToDB > 0:
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
    if ReagentLot == "":
        ReagentLot = "NA1"
    ReagentCountDIC = {ReagentLot:ReagentCount}
    k = 0
    while k < len(SendBuffer):
        Reagenttmp = SendBuffer[k]
        if Reagenttmp["id"] == ReagentID + ReagentName :
            #不重复记录
            if ReagentLot not in Reagenttmp["Reagent"]:
                Reagenttmp["LotCount"] = Reagenttmp["LotCount"] + 1
                Reagenttmp["TestCount"] = Reagenttmp["TestCount"] + int(ReagentCount)
                Reagenttmp["Reagent"][ReagentLot] = ReagentCount
                SendBuffer[k] = Reagenttmp
            break
        k = k + 1
    if k == len(SendBuffer):
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
            sendres = tcpconnect(recvserverip, int(recvserverport))
            while len(SendBuffer) > 0 :
                text = SendBuffer.pop(0)
                id = SendBufferID.pop(0)
                SendDic[id] = text
                NeedSend = True
            if NeedSend == True:
                tempsend = {}
                tempsend["basic_info"] = {}
                tempsend["basic_info"]["instrumentname"] = instrumentna
                tempsend["basic_info"]["update_time"] = str(datetime.datetime.now())
                tempsend["testmap"] = SendDic
                sendcontent = str.encode(json.dumps(tempsend))
                sendres.send(sendcontent)
                print(str(tempsend))
                r = "a"
                while type(r) != float:
                    r = bytes.decode(sendres.recv(102400))
                    try:
                        r = float(r)
                        print (r)
                    except:
                        sendres.send(sendcontent)
                        r = "false"
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

def SendReagentInfoFromDBToAptioByAPScheduler():
    global DICTestmap,ToCanbusSerial,HasSelected;
    print('SendReagentInfoFromDBToAptioByAPScheduler');
    try:
        if len(DICTestmap) > 0 and HasSelected :
            testmap,reagentinfo = MakeReagentMap(instrumentna,DICTestmap);
            if testmap != "":
                writelog(ToCanSerial.portstr + ' IS To CAN')
                s = binascii.a2b_hex(testmap)
                ToCanSerial.write(s)
                time.sleep(20)
                for t in reagentinfo:
                    s = binascii.a2b_hex(t)
                    ToCanSerial.write(s)
                    time.sleep(20)
        else:
            TimerSendReagentRequestByAPScheduler();
    except:
        print("Error");

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
        #sched.add_job(SerialRecieveReplyThreadByAPScheduler, 'interval', seconds=SchedulerTime_SerialCommunite,
        #          id='SerialRecieveReplyThreadByAPScheduler')
        sched.add_job(TimerSendReagentRequestByAPScheduler, 'interval', seconds=SchedulerTime_SyncReagent,
                  id='TimerSendReagentRequestByAPScheduler')
        if SchedulerTime_SendReagentToDB > 0:
            sched.add_job(SendReagentInfoToDbByAPScheduler, 'interval', seconds=SchedulerTime_SendReagentToDB,
                  id='SendReagentInfoToDbByAPScheduler')
        if SyncReagentFromDB == '1' :
            sched.add_job(SendReagentInfoFromDBToAptioByAPScheduler, 'interval', seconds=SchedulerTime_SendReagentToDB,
                  id='SendReagentInfoFromDBToAptioByAPScheduler')
        else:
            sched.add_job(TimerSendReagentRequestByAPScheduler, 'interval', seconds=SchedulerTime_SyncReagent,
                  id='TimerSendReagentRequestByAPScheduler')
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



#123
if __name__ == '__main__':
    global logFilePath,SchedulerTime_SerialCommunite,SchedulerTime_SendReagentToDB,SchedulerTime_SyncReagent,SchedulerTime_KeepAlive,bInReagentAsync,bInSampleQueueCommand
    logFilePath = "//PythonTools//CentaurXPReagentAsync//" + time.strftime("%Y%m%d",time.localtime()) + "//"
    LoadConfig()
    InitSerialPort()
    bInReagentAsync = False
    bInSampleQueueCommand = False
    today = datetime.date.today()


    try:
        if os.path.exists(logFilePath) == False:
            os.mkdir(logFilePath)
    except:
        logFilePath = ""
    threads = []
    
    SerialTransmitT = threading.Thread(target=SerialRecieveReplyThreadByThread)
    threads.append(SerialTransmitT)
    

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



        
