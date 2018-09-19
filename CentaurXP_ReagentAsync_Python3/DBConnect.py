import pymysql;
from Setting import GetSetting;
from SerialOnRasperry import writelog;
global dbname,dbhost,dbuser,dbpass;

def LoadConfig():
    global dbname,dbhost,dbuser,dbpass;
    dbname = GetSetting('DB','DBName','sys_info');
    dbhost = GetSetting('DB','DBHost','127.0.0.1');
    dbport = GetSetting('DB','DBPort','3306');
    dbuser = GetSetting('DB','Username','root');
    dbpass = GetSetting('DB','Password','root');

def ConnectDB():
    global dbname,dbhost,dbuser,dbpass;
    dbconnect = pymysql.connect(dbhost,dbuser,dbpass,dbname);
    return dbconnect;

def FetchData(sql):
    connect = ConnectDB();
    cur = connect.cursor()
    try:
        cur.execute(sql)
        result = cur.fetchall();
    except:
        print ("Error: unable to fetch data");
        writelog("DB: " + "unable to fetch data");
        result = [];
        print(sql)
    connect.close();
    return result;
        
def ExecuteSQL(sql):
    connect = ConnectDB();
    cur = connect.cursor()
    try:
        cur.execute(sql)
        connect.commit();
    except:
        cur.rollback()
        print ("Error: Error to Execute SQL!");
        writelog("DB: " + "Error to Execute SQL!");
    connect.close();
