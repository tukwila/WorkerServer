# In this version, ver1_logicdbfile/ver2_logicdbfile/xodrfile/paramfile these files can be search in fileserver

import SimpleHTTPServer
import SocketServer
import os,pwd,subprocess
import json
import logging
import time
import re
import datetime
import requests
import sys
import pprint
sys.path.append("..")

root_dir = os.path.dirname(os.path.realpath(__file__))

OMS_SERVER_IP = '10.68.1.181'
OMS_SERVER_PORT = 8888

#qi_toolkit working path
QI_TOOLKIT_WORKING_PATH = "/tmp/qi_data"

logging.basicConfig(level = logging.INFO,
                    format = '%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                    datefmt = '%a, %d %b %Y %H:%M:%S',
                    filename = '%s/logs/qi_worker.log' % (root_dir),
                    filemode = 'a'
                    )

class QI_utils(object):

    def find_logicdbfile_in_fileserver(self,fileserver,task,testcase,version):
        logicDB_loc = 'report'
        testcase_root_url = fileserver + task + '/' + testcase + '/report/' + version
        res = requests.get(testcase_root_url)
        logicdb_file=re.findall('<a .*>(.*DB.*)</a>',res.content)
        if len(logicdb_file) == 0:
            testcase_root_url = fileserver + task + '/' + testcase + '/out/' + version + '/BackendServer/' 
            res = requests.get(testcase_root_url)
            logicdb_file=re.findall('<a .*>(.*logicDB.*)</a>',res.content)
            logicDB_loc = 'out'
        return logicdb_file[0],logicDB_loc

    def download_tar_files(self,fileserver,task,testcase,version,filepath,logicDB_loc,storepath):
        '''
        download QI data files from OMS fileserver to QI server
        filepath : file path in file server, such as: /task/testcase/report/version/logicDB.tar.gz or /pkg/xxx.xodr
        in fileserver file tree looks like as such:
        data
            --Task
                --testcase
                        --logs
                        --out
                            --version
                                --BackendServer
                                    --logicDB.tar.gz
                                --CloudServer
                                --Vehicle                    
                        --pkg
                            --rrm (xodr file)
                            --paramfile.txt
                            --xxx.json
                        --report
                                --version1
                                        --logicDB.tar.gz
                                        --QI_result.tar.gz
        '''
        testcase_root_url = fileserver + task + '/' + testcase
        if logicDB_loc == 'report':
            file_url = testcase_root_url + '/report/' + version + '/' + filepath
        if logicDB_loc == 'out':
            file_url = testcase_root_url + '/out/' + version + '/BackendServer/' + filepath
        try:
            #change current working path to store files, storepath = '../QI_test'
            os.chdir(storepath)
            curl_cmd = 'curl -O %s' % file_url
            logging.info("download_tar_files: %s" % curl_cmd)
            logging.info("download storage path: %s" % storepath)
            os.system(curl_cmd)
            os.chdir(root_dir)
        except Exception as e:
            logging.error("download %s failed, exception: %s " % (filepath,e))

    def find_xodr_in_fileserver(self,fileserver,task,testcase,version):
        testcase_root_url = fileserver + task + '/' + testcase + '/pkg'
        res = requests.get(testcase_root_url)
        xodr_file=re.findall('<a .*>(.*xodr)</a>',res.content)
        return xodr_file

    def download_rrm_file(self,fileserver,task,testcase,xodrfile,rrm_path):
        testcase_root_url = fileserver + task + '/' + testcase
        file_url = testcase_root_url + '/pkg/' + xodrfile
        try:
            os.chdir(rrm_path)
            curl_cmd = 'curl -O %s' % file_url
            logging.info("download_rrm_file: %s" % curl_cmd)
            logging.info("download storage path: %s" % rrm_path)
            os.system(curl_cmd)
            os.chdir(root_dir)
        except Exception as e:
            logging.error("download %s failed, exception: %s " % (xodrfile,e))

    def get_paramfile_from_http_fs(self,fileserver,task,testcase):
        http_url = fileserver + task + '/' + testcase + '/pkg/paramfile.json'
        res = requests.get(http_url,stream=True)
        print res.content
        paramfile = str(json.loads(res.content)['task_param'])
        if paramfile == 'null':
            return paramfile
        else:
            #download json file to qi server
            testcase_root_url = fileserver + task + '/' + testcase + '/pkg'
            json_url = testcase_root_url + '/' + paramfile
            try:
                os.chdir(os.getcwd() + '/' + task + '_' + testcase + '/')
                curl_cmd = 'curl -O %s' % json_url
                os.system(curl_cmd)
                os.chdir(root_dir)
                return task + '_' + testcase + '/' + paramfile
            except Exception as e:
                logging.error("download %s failed, exception: %s " % (json_url,e))
            

    #upload qi result to file server
    def upload_to_file_server(self,fileserver,task,testcase,version,file_path):
        '''
        upload QI result to file server.
        '''
        testcase_root_url = fileserver + task + '/' + testcase
        file_upload_url = testcase_root_url + '/report/' + version + '/'
        logging.info("upload file '%s' to '%s'" %(file_path, file_upload_url))
        cmd = "curl %s --upload-file %s" % (file_upload_url, file_path)
        print 'upload cmd: %s' % cmd
        self.exec_cmd(cmd, retry=5)

    #upload qi_repoortMeta.json to report/2D or report/3D
    def upload_qi_reportMeta(self,fileserver,task,testcase,version,dimention,file_path):
        file_upload_url = fileserver + task + '/' + testcase + '/report/' + version + '/' + dimention + '/'
        logging.info("upload qi_repoortMet file '%s' to '%s'" %(file_path, file_upload_url))
        cmd = "curl %s --upload-file %s" % (file_upload_url, file_path)
        self.exec_cmd(cmd, retry=5)
    

    def exec_cmd(self, cmd, stdin=None, isbreak=True, retry=0):
        '''
        the public execute command function on the local host.
        '''
        # logging.info("<<<< %s" % cmd)
        # exit_status = os.system("%s >>%s 2>&1" % (cmd, self.log_file_path))
        subp = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        out, err = subp.communicate(stdin)
        stdout = self._append_message('', out)
        stderr = self._append_message('', err)
        exit_status = subp.wait()
        # logging.info("stdout: %s : %s" % (cmd, stdout))
        # logging.info("stderr: %s : %s" % (cmd, stderr))
        logging.info(">>>> %s : %s" % (cmd, exit_status))
        if exit_status != 0:
            if retry > 0:
                exit_status,stdout = self.exec_cmd(cmd, isbreak=isbreak, retry=retry - 1)
        return [exit_status,stdout]

    def _append_message(self, str1, str2):
        '''
        append message
        :param str1:
        :param str2:
        :return:
        '''
        return str(str1) + str(str2)

    def logging(self, msg):
        '''
        recorde log message.
        '''
        time_stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_file_path = ""
        os.system("echo '[%s] %s' >> %s " %
                  (time_stamp, msg, self.log_file_path))


    def untar_files(self, logicdb_storepath, logicdbfile,version):
        '''
        untar logic db files
        TBD: logicDB tar package should tar correctly in OMS backup_backend.py
        '''
        if not os.path.exists(logicdb_storepath+version) or not os.path.isdir(logicdb_storepath+version):
            os.makedirs(logicdb_storepath+version)
        tar_cmd = 'tar -xf %s -C %s' % (logicdb_storepath+logicdbfile,logicdb_storepath+version)
        os.system(tar_cmd)
        ver_db_paths= ''
        cmd = 'find %s%s -name *.db' % (logicdb_storepath,version)
        temp =os.popen(cmd).read().split()
        for dirlist in temp:
            if re.search('master',dirlist):
                continue
            else:
                ver_db_paths = dirlist + ' ' + ver_db_paths
        ver_db_paths = ver_db_paths.rstrip()
        #logging.info('ver_db_paths: %s' % ver_db_paths)
        return ver_db_paths
    
    def create_result_path(self,task,testcase,ver1,ver2):
        '''
        create resullt path
        QI_server file folder tree:
        QIWorker_server
            --QI_test (logicDB)
            --qi-tools
            --rrm (xodr)
            --task_testcase_ver1_ver2_runtime (QI result)
            --QIHTTPServer.py
        '''



        root_dir = os.path.dirname(os.path.realpath(__file__))
        runtime = time.strftime("%Y-%m-%d-%H%M")
        os.chdir(root_dir)

        #get SetZcoordinateToZero value
        AlgoConfig_filepath = root_dir + '/qi-tools/config'
        SetZcoordinateToZero = self.get_SetZcoordinateToZero_value(AlgoConfig_filepath)
        dimention = '2D'
        if SetZcoordinateToZero == 'SetZcoordinateToZero=0':
            dimention = '3D'
        if SetZcoordinateToZero == 'SetZcoordinateToZero=1':
            dimention = '2D'

        result_path = root_dir + '/' + task + '_' + testcase + '_' + ver1 + '_' + ver2 + '_' + runtime + '_' + dimention

        ver1_result_path = result_path+'/'+ ver1 + '_result'
        os.makedirs(ver1_result_path)

        ver2_result_path = result_path+'/'+ ver2 + '_result'
        os.makedirs(ver2_result_path)

        os.makedirs(ver1_result_path + '/tc_result')
        os.makedirs(ver1_result_path + '/tp_result')
        os.makedirs(ver1_result_path + '/geo_json')
        os.makedirs(ver1_result_path + '/KML')
        
        os.makedirs(ver2_result_path + '/tc_result')
        os.makedirs(ver2_result_path + '/tp_result')
        os.makedirs(ver2_result_path + '/geo_json')
        os.makedirs(ver2_result_path + '/KML')
        return result_path

    def get_SetZcoordinateToZero_value(self,path):
        file_path = path + '/AlgoConfig.ini'
        check_cmd = 'grep \'SetZcoordinateToZero\' %s' % file_path
        check_result = os.popen(check_cmd).read().strip()
        return check_result

    def run_tc_tp_by_qi_toolkit(self, fileserver, task, testcase, rdb_current_version, rdb_previous_version, qi_test):
        '''
        launching QI_ToolKit to evaluate test case's Logicdb by docker.
        :param fileserver: 
        :param task: 
        :param testcase:
        :param rdb_current_version: 
        :param rdb_previous_version: 
        :param qi_test
        '''
        #Initial working directory
        logging.info("Initial working directory")
        qi_task_data_base_path = QI_TOOLKIT_WORKING_PATH + os.path.sep + task
        if os.path.exists(qi_task_data_base_path):
            self.exec_cmd("rm -rf %s" % qi_task_data_base_path)
        self.exec_cmd("mkdir -p %s" % qi_task_data_base_path)
        #-initial test case input data directory
        previous_tc_input_data_path = qi_task_data_base_path + os.path.sep + rdb_previous_version \
            + os.path.sep + testcase
        current_tc_input_data_path = qi_task_data_base_path + os.path.sep + rdb_current_version \
            + os.path.sep + testcase
        self.exec_cmd("mkdir -p %s/RRM" % previous_tc_input_data_path)
        self.exec_cmd("mkdir -p %s/SRM" % previous_tc_input_data_path)
        self.exec_cmd("mkdir -p %s/OUT/kml" % previous_tc_input_data_path)
        self.exec_cmd("mkdir -p %s/RRM" % current_tc_input_data_path)
        self.exec_cmd("mkdir -p %s/SRM" % current_tc_input_data_path)
        self.exec_cmd("mkdir -p %s/OUT/kml" % current_tc_input_data_path)
        #-initial test plan input data directory, due to singal case plan so that test plan id is test case id.
        test_plan_input_data_path = qi_task_data_base_path + os.path.sep + testcase
        self.exec_cmd("mkdir -p %s/%s" % (test_plan_input_data_path, rdb_previous_version))
        self.exec_cmd("mkdir -p %s/%s" % (test_plan_input_data_path, rdb_current_version))
        self.exec_cmd("mkdir -p %s/%s" % (test_plan_input_data_path, "OUT"))

        #LogicDB file preprocess
        logging.info("LogicDB file preprocess")
        for rdb_version in [rdb_previous_version, rdb_current_version]:
            #download logic db file
            logicdbfile,logicDB_loc = self.find_logicdbfile_in_fileserver(fileserver,task,testcase,rdb_version)
            logicdb_storepath = qi_task_data_base_path + os.path.sep + rdb_version \
                + os.path.sep + testcase + os.path.sep + "SRM"
            logging.info("Download logic db file : %s" % logicdb_storepath)
            self.download_tar_files(fileserver,task,testcase,rdb_version,logicdbfile,logicDB_loc,logicdb_storepath)
            #untar logic db
            self.exec_cmd("tar -xzvf %s/%s -C %s && rm %s/%s" % (logicdb_storepath, logicdbfile, logicdb_storepath, logicdb_storepath, logicdbfile))

        #RRM file preprocess
        xodrfile_exist = True
        for rdb_version in [rdb_previous_version, rdb_current_version]:
            #download rrm file
            xodrfile = self.find_xodr_in_fileserver(fileserver,task,testcase,rdb_version)
            logicdb_storepath = qi_task_data_base_path + os.path.sep + rdb_version \
                + os.path.sep + testcase + os.path.sep + "RRM"
            if len(xodrfile) != 0:
                self.download_rrm_file(fileserver,task,testcase,xodrfile[0],logicdb_storepath)
            else:
                xodrfile_exist = False

        #get and download AlgoConfig
        self.download_algo_cfg(fileserver,task,testcase,qi_task_data_base_path)

        #get and download paramfile.json
        self.download_param_cfg(fileserver,task,testcase,qi_task_data_base_path)
        
        #get and download algo lib for very special case
        self.download_algo_lib(fileserver,task,testcase,qi_task_data_base_path)

        #Checking the tc evaluation result if exist.
        qi_toolkit_version = self.get_qi_toolkit_version(qi_test)
        needs_evaluate_version_list = []
        rdb_pre_ver_eval_exist, rdb_pre_ver_eval_json_url, rdb_pre_ver_eval_db_url = self.qi_tc_executor_result_exist(fileserver, task, testcase, rdb_previous_version, qi_toolkit_version)
        rdb_cur_ver_eval_exist, rdb_cur_ver_eval_json_url, rdb_cur_ver_eval_db_url = self.qi_tc_executor_result_exist(fileserver, task, testcase, rdb_current_version, qi_toolkit_version)
        if not rdb_pre_ver_eval_exist:
            needs_evaluate_version_list.append(rdb_previous_version)
        else:
            loc_rdb_pre_ver_eval_json_path = previous_tc_input_data_path + os.path.sep + 'OUT' + \
                os.path.sep + testcase + '.json'
            loc_rdb_pre_ver_eval_db_path = previous_tc_input_data_path + os.path.sep + 'OUT' + \
                os.path.sep + testcase + '.db'
            self.download_file(loc_rdb_pre_ver_eval_json_path, rdb_pre_ver_eval_json_url)
            self.download_file(loc_rdb_pre_ver_eval_db_path, rdb_pre_ver_eval_db_url)
        if not rdb_cur_ver_eval_exist:
            needs_evaluate_version_list.append(rdb_current_version)
        else:
            loc_rdb_cur_ver_eval_json_path = current_tc_input_data_path + os.path.sep + 'OUT' + \
                os.path.sep + testcase + '.json'
            loc_rdb_cur_ver_eval_db_path = current_tc_input_data_path + os.path.sep + 'OUT' + \
                os.path.sep + testcase + '.db'
            self.download_file(loc_rdb_cur_ver_eval_json_path, rdb_cur_ver_eval_json_url)
            self.download_file(loc_rdb_cur_ver_eval_db_path, rdb_cur_ver_eval_db_url)

        #Launchling QI_Toolkit to process test case data.
        evaluation_failed_data = []
        qi_launcher_path = root_dir + os.path.sep + "qi-toolkit" + os.path.sep + "qi_launcher.sh"
        tc_launcher_function_name = "launch_tc_executor"
        for rdb_version in needs_evaluate_version_list:
            tc_launcher_function_paramters = "%s,%s,%s" % (task, rdb_version, testcase)
            logging.info("Launchling QI_Toolkit to process test case data : %s, %s" % (rdb_version, testcase))
            self.exec_cmd("%s -f %s -p %s -v %s" % (qi_launcher_path, tc_launcher_function_name, tc_launcher_function_paramters, qi_toolkit_version))
            #-checking test case evalution result
            tc_json_file_path = qi_task_data_base_path + os.path.sep + rdb_version \
                + os.path.sep + testcase + os.path.sep + "OUT" + os.path.sep + testcase + ".json"
            if not os.path.exists(tc_json_file_path):
                logging.error("%s file not exists" % tc_json_file_path)
                self.upload_tc_evaluation_result(fileserver, task, testcase, rdb_version, success=False)
                evaluation_failed_data.append(rdb_version)
            else:
                self.upload_tc_evaluation_result(fileserver, task, testcase, rdb_version, success=True)
        #-checking evaluation result.
        if 0 < len(evaluation_failed_data):
            raise Exception("%s %s data evalution failed." % (testcase, evaluation_failed_data))

        #Create qi-report-prarm.json
        logging.info("Create qi-report-prarm.json")
        param_file_path = test_plan_input_data_path + os.path.sep + "qi-report-param.json"
        self.exec_cmd("echo '{}' > %s" % param_file_path)
        recordAmount = self.get_testcase_record_amount(fileserver, task, testcase)
        if (qi_toolkit_version >= '2.5.0'):
            self.creat_qi_report_param_file_v2_5(param_file_path, task, rdb_previous_version, rdb_current_version, testcase, xodrfile_exist, recordAmount, qi_toolkit_version)
        else:
            self.creat_qi_report_param_file(param_file_path, task, rdb_previous_version, rdb_current_version, testcase, xodrfile_exist, recordAmount, qi_toolkit_version)
        
        #Launchling QI_Toolkit to process test plan data.
        #-get test case evalution result
        logging.info("Launchling QI_Toolkit to process test plan data.")
        for rdb_version in [rdb_previous_version, rdb_current_version]:
            org_tc_file_path = qi_task_data_base_path + os.path.sep + rdb_version \
                + os.path.sep + testcase + os.path.sep + "OUT" + os.path.sep + testcase + ".json"
            des_tc_file_path = qi_task_data_base_path + os.path.sep + testcase \
                + os.path.sep + rdb_version + os.path.sep + testcase + ".json"
            self.exec_cmd("cp %s %s" % (org_tc_file_path, des_tc_file_path))

        for rdb_version in [rdb_previous_version, rdb_current_version]:
            org_tc_db_file_path = qi_task_data_base_path + os.path.sep + rdb_version \
                + os.path.sep + testcase + os.path.sep + "OUT" + os.path.sep + testcase + ".db"
            des_tc_db_file_path = qi_task_data_base_path + os.path.sep + testcase \
                + os.path.sep + rdb_version + os.path.sep + testcase + ".db"
            self.exec_cmd("cp %s %s" % (org_tc_db_file_path, des_tc_db_file_path))
        #-launch tp executor
        qi_launcher_path = root_dir + os.path.sep + "qi-toolkit" + os.path.sep + "qi_launcher.sh"
        tp_launcher_function_name = "launch_tp_executor"
        tp_launcher_function_paramters = "%s,%s,%s,%s" % (task, rdb_previous_version, rdb_current_version, testcase)
        self.exec_cmd("%s -f %s -p %s -v %s" % (qi_launcher_path, tp_launcher_function_name, tp_launcher_function_paramters, qi_toolkit_version))
        #-checking test plan & report result
        report_file_path = test_plan_input_data_path + os.path.sep + "OUT" + os.path.sep \
            + "Report" + os.path.sep + "report.html"
        index_file_path = test_plan_input_data_path + os.path.sep + "OUT" + os.path.sep \
            + "Report" + os.path.sep + "index.html"
        if ((not os.path.exists(report_file_path)) and (not os.path.exists(index_file_path))):
            logging.error("%s file not exists" % report_file_path)
            raise Exception("%s report generation failed" % testcase)
        
        #Package report result.
        logging.info("Package report result.")
        package_file_name = testcase + '_' + rdb_current_version + '_' \
             + rdb_previous_version + '_' + time.strftime("%Y%m%d%H%M%S") + '_by_' + qi_toolkit_version +'.tar.gz'
        package_file_tp_out = test_plan_input_data_path + os.path.sep + "OUT"
        report_tar_file_path = test_plan_input_data_path + os.path.sep + package_file_name
        tar_cmd = "tar -C %s -czf %s Report" % (package_file_tp_out, report_tar_file_path)
        self.exec_cmd(tar_cmd)
        #-upload result package to file server.
        logging.info("Upload result package to file server")
        self.upload_to_file_server(fileserver, task, testcase, rdb_current_version, report_tar_file_path)

    def download_param_cfg(self, fileserver,task,testcase,qi_task_data_base_path):
        '''
        Downloading param_cfg file form file server
        '''
        testcase_config_file_url = fileserver + task + "/" + testcase + "/pkg/config.json"
        try:
            tc_config = requests.get(testcase_config_file_url,stream=True)
            param_cfg_file = json.loads(tc_config.content)['qi_param_cfg']
            param_cfg_file_url = fileserver + task + "/" + testcase + "/pkg/" + param_cfg_file
            param_cfg_file_path = qi_task_data_base_path + os.path.sep + "param_cfg.json"
            self.download_file(param_cfg_file_path, param_cfg_file_url)
        except Exception as e:
            logging.warning("%s not specified param_cfg.json, %s" % (testcase, e))

    def download_algo_cfg(self, fileserver,task,testcase,qi_task_data_base_path):
        '''
        Downloading algo_cfg file form file server
        '''
        testcase_config_file_url = fileserver + task + "/" + testcase + "/pkg/config.json"
        try:
            tc_config = requests.get(testcase_config_file_url,stream=True)
            algo_cfg_file = json.loads(tc_config.content)['qi_algo_cfg']
            algo_cfg_file_url = fileserver + task + "/" + testcase + "/pkg/" + algo_cfg_file
            algo_cfg_file_path = qi_task_data_base_path + os.path.sep + "algo_cfg.ini"
            self.download_file(algo_cfg_file_path, algo_cfg_file_url)
        except Exception as e:
            logging.warning("%s not specified algo_cfg.json" % testcase)

    def download_algo_lib(self, fileserver,task,testcase,qi_task_data_base_path):
        '''
        Downloading algo_lib file form file server
        '''
        testcase_config_file_url = fileserver + task + "/" + testcase + "/pkg/config.json"
        try:
            tc_config = requests.get(testcase_config_file_url,stream=True)
            algo_lib_file = json.loads(tc_config.content)['qi_algo_lib']
            algo_lib_file_url = fileserver + task + "/" + testcase + "/pkg/" + algo_lib_file
            algo_lib_file_path = qi_task_data_base_path + os.path.sep + algo_lib_file
            self.download_file(algo_lib_file_path, algo_lib_file_url)
        except Exception as e:
            logging.warning("%s not specified qi_algo_lib" % testcase)
            
    def download_file(self, loc_file_path, rmt_file_url):
        '''
        downloading file from remote file server.
        '''
        curl_cmd = 'curl -o %s %s' % (loc_file_path, rmt_file_url) 
        exit_status,stdout = self.exec_cmd(curl_cmd)
        if (0 != exit_status):
            err_msg = "Download file %s failed, exit_status=%s" % (rmt_file_url, exit_status)
            logging.error(err_msg)
            raise Exception(err_msg)

    def qi_tc_executor_result_exist(self, fileserver, task, testcase, rdb_version, qi_toolkit_version):
        '''
        checking the test case evaluation result if exist.
        '''
        exist = False
        tc_executor_result = ""
        tc_executor_result_db = ""
        result_root_url = fileserver + task + '/' + testcase + '/report/' + rdb_version + '/' + 'qi_tc_executor_result'
        res = requests.get(result_root_url)
        if (200 == res.status_code):
            res_qi_toolkit_version_list = re.findall('<a .*>(.*)/</a>',res.content)
            print res_qi_toolkit_version_list
            try :
                res_qi_toolkit_version_list.index(qi_toolkit_version)
                #get tc_executor_result json
                result_qi_ver_url = result_root_url + '/' + qi_toolkit_version
                res_qi_ver = requests.get(result_qi_ver_url)
                if (200 == res_qi_ver.status_code):
                    success_result_list = re.findall('<a .*>(\d*)/</a>',res_qi_ver.content)
                    if (0 == len(success_result_list)):
                        raise Exception("no valid result")
                    print success_result_list
                    success_result_list.sort()
                    latest_result = success_result_list[-1]
                    #checking latest_result is valid.
                    result_qi_success_url = result_qi_ver_url + '/' + latest_result
                    res_qi_success = requests.get(result_qi_success_url)
                    if (200 == res_qi_success.status_code):
                        done_file_list = re.findall('<a .*>done</a>',res_qi_success.content)
                        if (0 == len(done_file_list)):
                            raise Exception("this %s evaluation result is invalid, the data not completly" % latest_result)
                        result_json_file_list = re.findall('<a .*>%s.json</a>' % testcase,res_qi_success.content)
                        if (0 == len(result_json_file_list)):
                            raise Exception("this evaluation result invalid no %s.json file" % testcase)
                        tc_executor_result = result_qi_success_url + '/' + "%s.json" % testcase
                        tc_executor_result_db = result_qi_success_url + '/' + "%s.db" % testcase
                        exist = True
                    else:
                        raise Exception("Get url page %s failed" % result_qi_success_url)
                else:
                    raise Exception("Get url page %s failed" % result_qi_ver_url)
            except Exception as e:
                logging.info("The %s evaluation result not exist. %s" % (qi_toolkit_version, e))
        else:
            logging.info("The test case not any evaluation result. res.status_code=%s" % res.status_code)
        return exist,tc_executor_result,tc_executor_result_db

    def get_qi_toolkit_version(self, qi_test):
        '''
        get qi_toolkit version
        '''
        try:
            return qi_test['qi_tool_ver']
        except Exception as e:
            raise Exception("Get QI-Tools version exception %s" % e)

    def upload_tc_evaluation_result(self, fileserver, task, testcase, rdb_version, success=True):
        '''
        Upload the evaluation result into FileServer
        :param fileserver:
        :param task:
        :param testcase:
        :param rdb_version:
        :param toolkit_version:
        '''
        logging.info("Backup %s evaluation result" % testcase)
        #test case evaluation result path
        org_result_loc_path = QI_TOOLKIT_WORKING_PATH + os.path.sep + task + os.path.sep + rdb_version \
            + os.path.sep + testcase + os.path.sep + "OUT"
        #get toolkit_version
        qi_toolkit_version = "0.0.0"
        qi_toolkit_version_file = org_result_loc_path + os.path.sep + "qi_toolkit_version.txt"
        if not os.path.exists(qi_toolkit_version_file):
            raise Exception("The qi_toolkit_version.txt file not exists, backup result failed.")
        with open(qi_toolkit_version_file) as f:
            qi_toolkit_version = f.readline().strip()
            logging.debug("qi_toolkit_version = %s" % qi_toolkit_version)
        #the path of in the FileServer
        time_stmp = time.strftime("%Y%m%d%H%M%S")
        if not success:
            time_stmp += "_failed"
        dst_result_rmt_path = fileserver + task + '/' + testcase + '/' + "report" \
            + '/' + rdb_version + '/' + 'qi_tc_executor_result' + '/' + qi_toolkit_version + '/' + time_stmp
        #upload file
        for f_name in os.listdir(org_result_loc_path):
            path_org_file = org_result_loc_path + os.path.sep + f_name
            if os.path.isfile(path_org_file):
                path_dst_file = dst_result_rmt_path + '/' + f_name
            elif os.path.isdir(path_org_file):
                if 0 == len(os.listdir(path_org_file)):
                    continue
                #packe up dir to tar file.
                tar_file_name = f_name + ".tar.gz"
                path_dst_file = dst_result_rmt_path + '/' + tar_file_name
                path_org_file = org_result_loc_path + os.path.sep + tar_file_name
                cmd = "tar -C %s -czf %s %s" % (org_result_loc_path, path_org_file, f_name)
                self.exec_cmd(cmd)
            else:
                continue
            logging.info("Upload file '%s' to '%s'" %(path_org_file, path_dst_file))
            cmd = "curl %s --upload-file %s" % (path_dst_file, path_org_file)
            self.exec_cmd(cmd, retry=5)
        #upload finished tag file
        cmd = "touch %s/done && curl %s/done --upload-file %s/done && rm %s/done" % \
            (org_result_loc_path, dst_result_rmt_path, org_result_loc_path, org_result_loc_path)
        self.exec_cmd(cmd)
        
    def get_testcase_record_amount(self, fileserver, task, testcase):
        '''
        Get amount of test case from fileserver
        :param fileserver:
        :param task:
        :param testcase:
        '''
        recordAmount = 0
        try:
            testcase_pkg_url = "%s/%s/%s/pkg" % (fileserver, task, testcase)
            res = requests.get(testcase_pkg_url)
            record_files=re.findall('<li><a .*/</a>',res.content)
            recordAmount = len(record_files)
        except Exception as e:
            logging.error("Get amount of test case failed : %s \n %s" % (testcase_pkg_url, e))
        return recordAmount


    def creat_qi_report_param_file_v2_5(self, target_param_file_path, tp_name, rdb_previous_version, rdb_current_version, tc_name, rrm_exist, recordAmount, qi_tool_ver):
        '''
        careting qi-report-param.json for qi > 2.5.0 report generation.
        :param tp_name: 
        :param rdb_previous_version: 
        :param rdb_current_version:
        :param tc_names:
        '''
        logging.info("Generate the qi-report-file : %s" % target_param_file_path)
        #json module file
        param_module_file_path = root_dir + os.path.sep + "qi-toolkit" + os.path.sep \
            + "qi-report-param_2.5.0.json"
        with open(param_module_file_path, "r") as f_module_param:
            param_module_file = json.load(f_module_param)
        #update json file
        param_module_file['currentVersion'] = rdb_current_version
        param_module_file['previousVersion'] = rdb_previous_version
        param_module_file['location'] = "Chengdu Lib, China"
        param_module_file['document'] = "V1.0"
        d_now = datetime.datetime.now()
        param_module_file['revisionDate'] = "%s" % d_now.strftime("%Y-%m-%d %H:%M:%S")
        #swVersion
        # qi_tool_ver = self.get_qi_toolkit_version()
        #testPlanDescription
        param_module_file['testPlan'] = {
            "testPlanID": "%s" % tc_name,
            "testPlanName": "%s" % tc_name,
            "testPlanTarget": "For RoadDB %s data quality regression test." % rdb_current_version,
            "link": "#"
            }
        #test cases
        param_module_file['testCases'][0]['testCaseId'] = tc_name
        param_module_file['testCases'][0]['testCaseName'] = tc_name
        param_module_file['testCases'][0]['recordAmount'] = recordAmount
        param_module_file['testCases'][0]['measureCategories'] = "ALL"
        param_module_file['testCases'][0]['rrmAvailable'] = rrm_exist
        param_module_file['testCases'][0]['currentQmdb'] = "/data/input/input/%s/%s/%s.db" % (tc_name, rdb_current_version, tc_name)
        param_module_file['testCases'][0]['previousQmdb'] = "/data/input/input/%s/%s/%s.db" % (tc_name, rdb_previous_version, tc_name)
        #The target save file"
        with open(target_param_file_path, 'w') as f_target_param:
            json.dump(param_module_file, f_target_param, indent=2)

    def creat_qi_report_param_file(self, target_param_file_path, tp_name, rdb_previous_version, rdb_current_version, tc_name, rrm_exist, recordAmount, qi_tool_ver):
        '''
        careting qi-report-param.json for qi report generation.
        :param tp_name: 
        :param rdb_previous_version: 
        :param rdb_current_version:
        :param tc_names:
        '''
        logging.info("Generate the qi-report-file : %s" % target_param_file_path)
        #json module file
        param_module_file_path = root_dir + os.path.sep + "qi-toolkit" + os.path.sep \
            + "qi-report-param.json"
        with open(param_module_file_path, "r") as f_module_param:
            param_module_file = json.load(f_module_param)
        #update json file
        param_module_file['currentVersion'] = rdb_current_version
        param_module_file['previousVersion'] = rdb_previous_version
        param_module_file['testPlanReference']['text'] = tc_name
        param_module_file['location'] = "Chengdu Lib, China"
        param_module_file['document'] = "V1.0"
        d_now = datetime.datetime.now()
        param_module_file['revisionDate'] = "%s" % d_now.strftime("%Y-%m-%d %H:%M:%S")
        #swVersion
        # qi_tool_ver = self.get_qi_toolkit_version()
        for x in xrange(len(param_module_file['swVersion'])):
            if param_module_file['swVersion'][x]["tool"] == "QI Tool":
                param_module_file['swVersion'][x]["version"] = qi_tool_ver
                param_module_file['swVersion'][x]["date"] = d_now.strftime("%Y-%m-%d")
            if param_module_file['swVersion'][x]["tool"] == "Report Generator":
                param_module_file['swVersion'][x]["version"] = qi_tool_ver
                param_module_file['swVersion'][x]["date"] = d_now.strftime("%Y-%m-%d")
        #testPlanDescription
        for i in xrange(len(param_module_file['testPlanDescription'])):
            if param_module_file['testPlanDescription'][i]["item"] == "Plan ID":
                param_module_file['testPlanDescription'][i]["description"] = tc_name
            if param_module_file['testPlanDescription'][i]["item"] == "Plan Name":
                param_module_file['testPlanDescription'][i]["description"] = tc_name
            if param_module_file['testPlanDescription'][i]["item"] == "Plan target":
                param_module_file['testPlanDescription'][i]["description"] = "For RoadDB %s data quality regression test." % rdb_current_version
            if param_module_file['testPlanDescription'][i]["item"] == "Number of test cases":
                param_module_file['testPlanDescription'][i]["description"] = "Amount of the cases : 1"
        #testCases
        param_module_file['testCases'] = [
                {
                    "testCaseId":"%s" % tc_name, 
                    "description":"%s" % "N/A", 
                    "recordAmount":"%s" % recordAmount,
                    "measureCategory":"ALL",
                    "rrmAvailability":"%s" % rrm_exist
                }
            ]
        #testPlanResults
        param_module_file['testPlanResults'] = [{
                    "version":"%s" % rdb_current_version,
                    "path":"/data/input/output/%s/%s/tp.json" % (tc_name, rdb_current_version),
                    "testCaseResults":[
                        {
                            "testCaseId":"%s" % tc_name,
                            "path":"/data/input/input/%s/%s/%s.json" % (tc_name, rdb_current_version, tc_name)
                        }
                    ]
                },
                {
                    "version":"%s" % rdb_previous_version,
                    "path":"/data/input/output/%s/%s/tp.json" % (tc_name, rdb_previous_version),
                    "testCaseResults":[
                        {
                            "testCaseId":"%s" % tc_name,
                            "path":"/data/input/input/%s/%s/%s.json" % (tc_name, rdb_previous_version, tc_name)
                        }
                    ]
                }
            ]
        #The target save file"
        with open(target_param_file_path, 'w') as f_target_param:
            json.dump(param_module_file, f_target_param, indent=2)

    def remove_files(self,task):
        root_dir = os.path.dirname(os.path.realpath(__file__))
        os.chdir(root_dir)
        cmd = 'rm -rf %s*' % task
        os.system(cmd)
        cmd = 'rm -rf *log.txt*'
        os.system(cmd)
        
    def testcase_callback(self,data):
        post_url = 'http://' + OMS_SERVER_IP + ':' + str(OMS_SERVER_PORT)
        data = json.dumps(data)
        header_dict = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Trident/7.0; rv:11.0) like Gecko',"Content-Type": "application/x-www-form-urlencoded"}
        res = requests.post(post_url,data=data,headers=header_dict)
        res.close()
        

import threading
import pymongo
from bson.objectid import ObjectId
#start mongod service in ubuntu: sudo mongod --dbpath=/var/lib/mongodb

class QI_server(object):

    def __init__(self):
        pass
    
    def start_single_thd_model(self):
        '''
        start single thread model.
        @author hang.cao
        '''
        logging.info("QI_server start")
        all_threads = []
        #qi_test_worker_thd
        thd_qi_test_worker = threading.Thread(target=self.qi_test_worker_single_thd, args=())
        thd_qi_test_worker.start()
        all_threads.append(thd_qi_test_worker)

        logging.info("All threads started.")

        for thd in all_threads:
            thd.join()

    def qi_test_worker_single_thd(self):
        '''
        A single thread worker function.
        '''
        while True:
            try:
                qi_test = None
                condition = {'QI_status':'submit'}
                qi_test = mongodb_find_one(condition)
                if qi_test == None:
                    time.sleep(5)
                    continue
                qi_test['QI_status'] = 'running'
                mongodb_update_one({"_id":qi_test["_id"]},qi_test)
            except Exception as e:
                logging.error("Get submit status qi task error: %s" % e)
                time.sleep(10)
                continue

            try:
                qi_object = QI_utils()
                tc_str = qi_test['testcase'].encode('utf-8') #transfer qi_test['testcase'] unicode to str
                _if_more_tc = re.search(',',tc_str)
                #start qi task execution
                logging.info("QI task execution started")
                qi_object.run_tc_tp_by_qi_toolkit(qi_test['fileserver'],qi_test['task'],qi_test['testcase'],qi_test['ver1'],qi_test['ver2'],qi_test)  
                qi_test['QI_status'] = 'done'
                mongodb_update_one({"_id":qi_test["_id"]},qi_test)
                logging.info("QI task execution successed")
            except Exception as e:
                logging.error('Qi task execution failed, exception: %s' % e)
                qi_test['QI_status'] = 'error'
                mongodb_update_one({"_id":qi_test["_id"]},qi_test)

def mongodb_find_one(condition):
    '''
    select function in mongodb
    '''
    collection = mongodb_collection()
    result = collection.find_one(condition)
    return result

def mongodb_update_one(condition, data):
    '''
    update one function in mongodb
    '''
    collection = mongodb_collection()
    result = collection.update_one(condition, {'$set':data}) 
    return result

def mongodb_find(condition):
    '''
    select function in mongodb
    '''
    collection = mongodb_collection()
    result = collection.find(condition) #result is class 'pymongo.cursor.Cursor' list
    return result

def mongodb_insert(data):
    '''
    insert function in mongodb
    '''
    collection = mongodb_collection()
    result = collection.insert(data) #insert function return mongodb data _id
    return result

def mongodb_collection():
    '''
    return mongdb collection
    '''
    collection = None
    while True:
        try:
            client = pymongo.MongoClient()
            db = client.QIWorker #connect to QIWorker db
            collection = db.postdata #connect to table postdata
            return collection
        except Exception as e:
            logging.error("Collecting MongoDB failed : %e" % e)
            time.sleep(10)
            continue

if __name__ == '__main__':
    # print "QI Server Start"
    qi_server = QI_server()
    qi_server.start_single_thd_model()

