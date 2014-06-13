#-*- coding:utf-8 -*-
import SocketServer,socket,time
import pickle,json
import os,commands,stat
from hashlib import md5
import db_connector
import redis_connector 
from triWeb.models import IP
recv_dir = 'recv/'

#server_address = '192.168.2.248'
block_list = []

import get_monitor_dic_fromDB
import getopt,sys
import key_gen,random_pass
proxy_monitor_dic = {}
is_server = 1

'''
monitor_dic = redis_connector.r.get('TriAquae_monitor_status')
if monitor_dic is not None:
    monitor_dic = json.loads(monitor_dic)
    #make sure all the hosts are in the monitor list
        for h in IP.objects.filter(status_monitor_on=True):
            if h.hostname not in monitor_dic.keys():
                     monitor_dic[h.hostname] = {}
else:
        monitor_dic = {}
        for h in IP.objects.filter(status_monitor_on=True):
                 monitor_dic[h.hostname] = {}


#print monitor_dic 
'''
def receive_data_by_size(sock,size):
    return_data = ''
    filename = time.time() 
    fp = open('/tmp/'+str(filename),'wb')
    restsize = size
    print "recving..."
    while 1:
        if(restsize > 8096):
            data = sock.recv(8096)
            return_data += data
        else:
            data = sock.recv(restsize)
            return_data += data
        if restsize ==0:
            break
        fp.write(data)
        restsize = restsize - len(data)
    print restsize
        #if restsize <= 0:
        #    break
    fp.close()
    print "receving is done...............",restsize                    
    return return_data
            
print '--------------server and trunk_servers to deal monitor info----------------'
class MyTCPHandler(SocketServer.BaseRequestHandler):
    def handle(self):
        def md5_file(filename):
                if os.path.isfile(filename):
                        m = md5()
                        with open(filename, 'rb') as f:
                                m.update(f.read())
                        return m.hexdigest()
                else:
                        return None
        def receive_data(sock):
            return_data ='' 
            while True:
                data = sock.recv(4096)
                #print '\033[36;1m%s\033[0m' %data
                if data == 'EndOfDataConfirmationMark':
                    print 'file transfer done==='
                    break
                return_data += data
            return return_data
        '''
        def receive_data_by_size(sock,size):
            return_data = ''
            filename = time.time() 
            fp = open('/tmp/'+str(filename),'wb')
            restsize = size
            print "recving..."
            while 1:
                if(restsize > 8096):
                    data = sock.recv(8096)
                    return_data += data
                else:
                    data = sock.recv(restsize)
                    return_data += data
                if restsize ==0:
                    break
                fp.write(data)
                restsize = restsize - len(data)
            print restsize
                #if restsize <= 0:
                #break
            fp.close()
            print "receving is done...............",restsize                    
            return return_data
        '''
        # self.request is the TCP socket connected to the client
        def RSA_verifyication(sock):
            raw_rsa_data = sock.recv(396)  #fixed key length
            #print '-------->',raw_rsa_data, len(raw_rsa_data)
            try:
                RSA_signal, encrypted_data,random_num_from_client = json.loads(  raw_rsa_data)
            except ValueError:
                print '\033[41;1mWrong data format from %s,close connection!\033[0m' %  self.client_address[0]
                return 0
            if RSA_signal == 'RSA_KEY_Virification':
                #encrypted_data = "iwTgqSzMcNOHauWdXXc+rgfbWt6IUXmdIXUqNUJ2U7FZKISc2WR2yAJrq7ldR3TxQEppWgIo/Ycj\nA5gl0fGDVvAEvV02CKZ3gZEI6fWpiMoy6ucpFFDyVAWUrpiXdUOVKxOsDXGgeOObgvd1jsEQCo4i\ncLCBTWDn0HfyQic+Btm1txXc7Nw9jknUCZx6Y8I+6JaIYjNRLwJ6kSMwpTsfP37lvrQfdUkWu3bX\npV9z3hHOQ6+A8rlK7fmL1zk75TXDCmnrLY88UIv6BL4zPXtim4BCD7PlOvDG296br0VIcvF5uhqr\ntj7zOcbA81P1JBFm1nMJqLv+SB5sit923v05XA==\n"
                try:
                    decrpted_data = key_gen.RSA_key.decrypt_RSA(key_gen.private_file,encrypted_data)
                    #print decrpted_data,'+++++++', random_num_from_client
                except ValueError:
                    decrpted_data = 'Incorrect decryption'
                if decrpted_data != random_num_from_client:
                    return 0
            else:
                return 0
        if RSA_verifyication(self.request) == 0: #didn't pass the RSA virification
            #if self.client_address[0] != server_address:
            err_msg= "\033[31;1mIP %s didn't pass the RSA virification,drop it!\033[0m" % self.client_address[0]
            pickle_data = '', err_msg
            self.request.sendall( pickle.dumps(pickle_data)  )
            print err_msg 
            block_list.append(self.client_address[0])
            if block_list.count(self.client_address[0]) > 5:
                print "Alert::malicious attack from:" , self.client_address[0]
        else:
            self.request.send('RSA_OK')
            #get connect client ip and port.
            client_ip,client_port=self.client_address
            #get client request data_type to do something
            self.data_type = self.request.recv(1024).strip()
            print "{} wrote:",self.client_address[0]
            if self.data_type.startswith('CMD_Excution|'):
                cmd= self.data_type.split('CMD_Excution|')[1]
                cmd_status,result = commands.getstatusoutput(cmd)
                print 'host:%s \tcmd:%s \tresult:%s' %(self.client_address[0], cmd, cmd_status)
                self.request.sendall(pickle.dumps( (cmd_status,result) ))
            elif self.data_type.startswith('RUN_Script|'):
                recv_data= self.data_type
                filename = "%s%s" %(recv_dir,recv_data.split('|')[1].strip())
                print '+++++|receiving file from server:',filename
                md5_key_from_client = self.data_type.split('|')[2]
                file_content = receive_data(self.request)
                print 'write data into file....'
                with open(filename, 'wb') as f:
                    f.write(file_content)
                md5_key= md5_file(filename )
                print '+++++|verfiying md5key---'
                if md5_key == md5_key_from_client:
                    print 'file transfer verification ok' 
                    self.request.send('FileTransferComplete')
                    os.system('chmod +rx %s ' % filename)
                    #os.chmod(filename,stat.S_IREAD+stat.S_IWOTH+stat.S_IXUSR+stat.S_IRWXO)
                    cmd = "nohup  %s > %s.log &" % (filename, filename)
                    print '\033[32;1mgoing to run script:\033[0m',cmd
                    result = os.system(cmd )
                    #print result,'||||+|||'
                else:
                    print "file not complete"
                    self.request.send('FileTransferNotComplete')
            elif self.data_type == "getMonitorStatusData":
                print "going to serialize Monitor_dic"
            elif self.data_type == 'getHardwareInfo':
                import Hardware_Collect_Script
                hardware_data = Hardware_Collect_Script.collectAsset() 
                self.request.sendall(hardware_data )
            elif self.data_type.startswith('MonitorDataRequest'):
                #第一次进行监控项信息的通信,还需要把主机名hostname传送过去？
                #self.request.send('ReadyToSendStatusData')
                if is_server:
                    #server deal
                    proxy_flag=self.data_type.split("|")
                    if proxy_flag[1] == 'proxy':
                        #处理代理请求
                        monitor_data=get_monitor_dic_fromDB.get_proxy_monitor_list(client_ip)
                    else:
                        #得到该ip的trunk_servers_id,如果没有数据怎么办,返回monitor_data为0
                        server_ip='10.168.7.105'
                        monitor_data=get_monitor_dic_fromDB.get_one_host_monitor_dir(client_ip,server_ip)
                    #monitor_data=''时，没有得到该ip的监控项
                    while 1:
                        if monitor_data:
                            print '---frist send monitor_data!---'
                            self.request.send(str(len(json.dumps(monitor_data))))
                            self.request.sendall(json.dumps(monitor_data))
                        else:
                            #没有该ip的监控项数据，返回0
                            #self.request.send("no_monitor")
                            self.request.send(json.dumps(monitor_data))
                            print 'ip has not monitor data......'
                        #接收客户端是否接收成功！注意这是阻塞等待接收？？？
                        self.data_status=self.request.recv(1024)
                        print self.data_status
                        if self.data_status:
                            #接收成功。
                            break
                        else:
                            pass
                else:
                    #proxy MonitorDataRequest as S  
                    #如果不存在IP的监控项？？client_ip,不能使用 global data_dic
                    while 1:
                        if proxy_monitor_dic.has_key(client_ip):
                            #发送监控项数据大小以及内容
                            monitor_data={}
                            monitor_data[client_ip] = proxy_monitor_dic[client_ip]
                            print monitor_data[client_ip]
                            self.request.send(str(len(json.dumps(monitor_data[client_ip]))))
                            self.request.sendall(json.dumps(monitor_data[client_ip]))
                        else:
                            #没有得到数据时，返回了一个'0'
                            print 'ip has not monitor status' 
                            self.request.send(str(0))
                        #接收客户端是否接收成功！，注意这是阻塞等待接收？？？
                        self.data_status=self.request.recv(1024)
                        print self.data_status
                        #接收成功。
                        if self.data_status:
                            print self.data_status
                            break
                        else:
                            pass
            #代理trunk_servers as local area network server optrate
            elif self.data_type.startswith('MonitorDataChange'):
                if is_server:
                    #监控数据改变通过tri_sender.py来主动发送,这里不实现
                    pass
                else:
                    #proxy MonitorDataChange as C->S发送连接状态,先以C接收，然后在以S分发
                    self.request.sendall('ReadyToReceiveData')
                    #get_proxy_monitor_dic
                    #data_size=self.request.recv(1024)
                    data_size=self.data_type.split("|")[1]
                    if data_size <=8096:
                        proxy_monitor_new_dic=json.loads(self.request.recv(8096))
                    else:
                        proxy_monitor_new_dic=json.loads(receive_data_by_size(self.request,int(data_size)))
                    #下发这些监控信息，得到监控数据中具有的ip
                    for k in proxy_monitor_new_dic.keys():
                        if k == 'ip':
                            client_monitor_dic=proxy_monitor_new_dic[k]
                            #向本地client端发送改变的监控信息
                            send_data(1,client_ip,9997,client_monitor_dic)
                            
            elif self.data_type.startswith('AssetsDataCollect'):
                self.request.send('ReadyToReceiveData')
                signal_flag = self.data_type.split("|")
                raw_data_from_client_size = int(signal_flag[1])
                if raw_data_from_client_size <= 8096:
                    raw_data_from_client = self.request.recv(8096)
                else:
                    raw_data_from_client = receive_data_by_size(self.request,raw_data_from_client_size)
                print '+++', raw_data_from_client
                assets_data = json.loads( raw_data_from_client )
                if is_server:
                    #处理收集到的资产信息，分为本地和代理发送过来的。
                    #if client_ip.startswith('10.') or client_ip.startswith('192.168.') or client_ip.startswith('172.[16,31].'):
                    assets_dic={}
                    if signal_flag[2] == 'proxy':
                        #代理的资产数据字典的处理,一个代理
                        for proxy_ip in assets_data.keys():
                            if proxy_ip == client_ip:
                                host_list=[]
                                for one_assets_data in assets_data[proxy_ip]:
                                    #首先要获取有几台主机信息
                                    client_hostname=one_assets_data['hostname']
                                    host_list.append(client_hostname)
                                for host in set(host_list):
                                    assets_dic[client_hostname]={}
                                
                                print assets_dic
                                
                                for one_assets_data in assets_data[proxy_ip]:
                                    #这里几条监控数据可能是同一台主机发送的，如何整理
                                    client_hostname=one_assets_data['hostname']
                                    #assets_dic.setdefault(client_hostname:{})
                                    #assets_dic={client_hostname:{}}
                                    for name,service_status in one_assets_data.items():
                                        if type(service_status) is dict:
                                            #说明name!=hostname的其他监控项,添加最后的监控时间
                                            service_status['last_check']=time.time()
                                            assets_dic[client_hostname][name]=service_status
                                            print assets_dic
                                    #如果hostname相同怎么吧？？？会重复覆盖，放到里面并？？
                            print assets_dic
                            
                        #最后处理资产收集到的字典设置
                    else:
                        #本地的,只是一个资产数据，进行数据基本处理
                        #{u'cpu_info': {'cpu_basicinfo': [{'cpu_id': u'CPU0', 'NumberOfCores': 2}]}, 'hostname': u'5245','mem_info':{}}
                        #旧的：{'load': {'status': 1}, 'hostname': 'localhost'}
                        client_hostname = assets_data['hostname']
                        assets_dic={client_hostname:{}}
                        #tmp={}
                        for name,service_status in assets_data.items():
                            #if type(service_status) is dict:
                            #说明name!=hostname的其他监控项,添加最后的监控时间
                            if name !='hostname':                                
                                service_status['last_check']=time.time()
                                #tmp[name]=service_status
                                assets_dic[client_hostname][name]=service_status
                        #assets_dic[client_hostname] = tmp
                        print assets_dic
                        print "------get conn from %s------\n" %client_hostname
                    # push status data into JSON file
                    '''
                    if client_hostname == 'localhost':
                        #print redis_connector.r.keys()
                        redis_connector.r['TriAquae_monitor_status'] = json.dumps(assets_dic)
                        #redis_connector.r.save()
                        print 'status inserted into JSON file'
                    '''
                else:
                    #proxy deal 向服务端发送数据HOST=?,PORT=? is_client=0
                    #把接收client端的数据放到redis中
                    timestemp=time.time()
                    redis_connector.r[timestemp]=json.dumps(assets_data)
                    '''
                    S_HOST='10.168.7.40'
                    S_PORT=9998
                    #何时向服务器端发送资产信息？？接到本地资产信息时发送，所有资产信息都收集到
                    #在之后更新的资产信息时，如何发送？？
                    client_hostname = client_ip
                    proxy_assets_dic={}
                    assets_dic={}
                    assets_dic[client_hostname]=assets_data
                    proxy_assets_dic['HOST'].append(assets_dic)
                    if client_hostname == HOST:
                        send_data(0,S_HOST,S_PORT,proxy_assets_dic)
                    '''
                    '''
                    for name,service_status in assets_data.items():
                        #print name,service_status
                        if type(service_status) is dict:
                            service_status['last_check'] = time.time()
                        assets_dic[client_hostname][name] =  service_status
                    proxy_assets_dic[HOST].append(assets_dic)
                    '''

            elif self.data_type == 'CollectStatusIntoJsonFile':
                print 'CollectStatusIntoJsonFile'
            elif self.data_type == 'datasizetest':
                print 'test'
                with open('tri_server.py') as f:
                    #data=f.read()
                    data=f.readlines()
                print type(data)
                self.request.sendall('1024')
                #time.sleep(0.5)
                self.request.send('OK')
                
#以代理的形式运行时
#the frist get monitor data所有以该代理为服务端的主机监控信息 server=(host,port)
#proxy MonitorDataRequest as C
def get_monitor_dic(host,port):
    '''第一次连接时，请求得到所有以该代理为服务端的主机监控信息'''
    try:
        req_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        req_s.connect((host, port))
        RSA_signal,random_num = 'RSA_KEY_Virification', str(random_pass.randomPassword(10))
        encrypted_data = key_gen.RSA_key.encrypt_RSA(key_gen.public_file,random_num)
        req_s.sendall(json.dumps( (RSA_signal,encrypted_data, random_num) )) 
        print 'get assets monitor configure info from server .... '
        #判断RSA认证结果
        RSA_status=req_s.recv(1024)
        if RSA_status == 'RSA_OK':
            #RSA认证通过后，进行监控数据请求
            req_s.send('MonitorDataRequest'+'|'+'proxy')
            #如果服务端查不到数据时，会发生异常。
            monitor_data_size=req_s.recv(1024)
            global proxy_monitor_dic
            if int(monitor_data_size) == 0:
                #该代理客户端没有被监控
                print 'proxy client has no monitor data...'
                req_s.send('get_info')
                return 0
            elif int(monitor_data_size) <= 8096:
                monitor_data = req_s.recv(8096)
            else:
                monitor_data =receive_data_by_size(req_s,int(monitor_data_size))
            req_s.send('get_info')
            proxy_monitor_dic=json.loads(monitor_data)
            print proxy_monitor_dic
            #send message
            print 'get monitor info.... '
            return proxy_monitor_dic
        else:
            print 'rsa error.......'
    except socket.error:
        print socket.error
    finally:
        req_s.close()
 
def send_data(is2client,host,port,data):
    try:
        send_cs=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        send_cs.connect((host, port))
        print 'start connect client/server host'
        RSA_signal,random_num = 'RSA_KEY_Virification', str(random_pass.randomPassword(10))
        encrypted_data = key_gen.RSA_key.encrypt_RSA(key_gen.public_file,random_num)
        print '1----'
        send_cs.send(json.dumps( (RSA_signal,encrypted_data, random_num) )) 
        print '\033[34;1m sending Monitor Data to proxy server  .... \033[0m'
        #判断RSA认证结果
        RSA_status=send_cs.recv(1024)
        if RSA_status == 'RSA_OK':
            #RSA认证通过后，发生数据状态，
            if is2client:
                #向client端分发监控项数据
                send_cs.send('MonitorDataChange'+'|'+str(len(data)))
                print 'MonitorDataChange........'
            else:
                #向server端上传资产数据
                send_cs.send('AssetsDataCollect'+'|'+str(len(data))+'|'+'proxy')
                print 'AssetsDataCollect...............'
            transfer_status=send_cs.recv(1024)
            if transfer_status=='ReadyToReceiveData':
                #向client/server host端发送该主机监控数据/或资产数据
                #send_cs.send(str(len(json.dumps(data))))
                send_cs.send( json.dumps(data) )
        else:
            print 'RSA Virification error!'
    except socket.error:
        print socket.error
    finally:
        send_cs.close()
        
if __name__ == "__main__":
    try:
        opts,args = getopt.getopt(sys.argv[1:], 'hvs:',['output=', 'foo=', 'fre='])
        print opts
    except getopt.GetoptError,err:
        print str(err)
        sys.exit(2)
    for o,a in opts:
        if o in ('-h', '--help'):
            print 'help'
            sys.exit(1)
        elif o in ('-v', '--version'):
            print 'version'
            sys.exit(0)
        elif o in ('-s', '--server'):
            if a in ('agent','proxy','trunk_server'):
                #global is_server
                #print a
                is_server=0
                S_HOST='10.168.7.105'
                S_PORT=9998
                #表示为代理服务,连接主server,得到监控数据
                get_monitor_dic(S_HOST,S_PORT)
        else:
            print '--------------------------server starting--------------------'

				print 'status inserted into JSON file'
				
		elif self.data == 'CollectStatusIntoJsonFile':
			print 'CollectStatusIntoJsonFile'
if __name__ == "__main__":
    HOST, PORT = "0.0.0.0", 9998
    # Create the server, binding to localhost on port 9998
    try:
        server = SocketServer.ThreadingTCPServer((HOST, PORT), MyTCPHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print 'prass ctrl+c,break'
        server.server_close()
        sys.exit()
    

