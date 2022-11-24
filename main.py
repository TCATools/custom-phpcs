# -*- encoding: utf8 -*-
"""
phpcs 工具
功能: php代码分析
用法: python3 main.py

本地调试步骤:
1. 添加环境变量: export SOURCE_DIR="xxx/src_dir"
2. 添加环境变量: export TASK_REQUEST="xxx/task_request.json"
3. 按需修改task_request.json文件中各字段的内容
4. 命令行cd到项目根目录,执行命令:  python3 src/main.py
"""

# 2020-12-24    kylinye    created

import os
import json
import subprocess
import sys
import xml.etree.ElementTree as ET


class PhpCs(object):
    """demo tool"""
    def __get_task_params(self):
        """
        获取需要任务参数
        :return:
        """
        task_request_file = os.environ.get("TASK_REQUEST")
        # task_request_file = "task_request.json"
        with open(task_request_file, 'r') as rf:
            task_request = json.load(rf)
        task_params = task_request["task_params"]

        return task_params

    def __get_dir_files(self, root_dir, want_suffix=""):
        """
        在指定的目录下,递归获取符合后缀名要求的所有文件
        :param root_dir:
        :param want_suffix:
                    str|tuple,文件后缀名.单个直接传,比如 ".py";多个以元组形式,比如 (".h", ".c", ".cpp")
                    默认为空字符串,会匹配所有文件
        :return: list, 文件路径列表
        """
        files = set()
        for dirpath, _, filenames in os.walk(root_dir):
            for f in filenames:
                if f.lower().endswith(want_suffix):
                    fullpath = os.path.join(dirpath, f)
                    files.add(fullpath)
        files = list(files)
        return files

    def config(self, rules):
        current_path = os.getcwd()
        rule_config_file = os.path.join(current_path, "config.xml")
        if os.path.exists(rule_config_file):
            os.remove(rule_config_file)
        
        # 1. 读取空模板
        model_config_file = os.path.join(current_path, "model.xml")
        if not os.path.exists(model_config_file):
            print("The template configuration file {model_config_file} does not exist, please check! ")
        open(rule_config_file, "wb").write(open(model_config_file, "rb").read())

        # 2. 写入规则
        config_data = ET.ElementTree(file=rule_config_file)
        root = config_data.getroot()
        for rule in rules:
            rule_node = ET.Element("rule")
            rule_node.set("ref", rule)
            if rule == "Squiz.Functions.FunctionDeclarationArgumentSpacing":
                properties_node = ET.Element("properties")
                property_node = ET.Element("property")
                property_node.set("name", "equalsSpacing")
                property_node.set("value", "1")
                properties_node.append(property_node)
                rule_node.append(properties_node)
            root.append(rule_node)
        config_data.write(rule_config_file)

        # 3. 
        f = open(rule_config_file, "r")
        lines = f.readlines()
        f.close()
        f = open(rule_config_file, "w")
        f.writelines('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.writelines(lines)
        f.close()

        return rule_config_file

    def run(self):
        """

        :return:
        """
        # 代码目录直接从环境变量获取
        source_dir = os.environ.get("SOURCE_DIR", None)
        # source_dir = "/Users/kylinye/Documents/UGit/example/Php_example/"
        print("[debug] source_dir: %s" % source_dir)

        # 其他参数从task_request.json文件获取
        task_params = self.__get_task_params()
        # 环境变量
        envs = task_params["envs"]
        print("[debug] envs: %s" % envs)
        # 前置命令
        pre_cmd = task_params["pre_cmd"]
        print("[debug] pre_cmd: %s" % pre_cmd)
        # 过滤路径
        re_exclude_path = task_params["path_filters"]["re_exclusion"]
        # 规则
        rules = task_params["rules"]
        # 查看path环境变量
        print("[debug] path: %s" % os.environ.get("PATH"))

        stdout_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stdout_file.txt")
        fs = open(stdout_path, "w")

        # ------------------------------------------------------------------ #
        # 增量扫描时,可以通过环境变量获取到diff文件列表,只扫描diff文件,减少耗时
        # 此处获取到的diff文件列表,已经根据项目配置的过滤路径过滤
        # ------------------------------------------------------------------ #
        # 需要扫描的文件后缀名
        want_suffix = (".php", ".inc", ".css", ".js")
        # 从 DIFF_FILES 环境变量中获取增量文件列表存放的文件(全量扫描时没有这个环境变量)
        diff_file_json = os.environ.get("DIFF_FILES")
        if diff_file_json:  # 如果存在 DIFF_FILES, 说明是增量扫描, 直接获取增量文件列表
            print("get diff file: %s" % diff_file_json)
            with open(diff_file_json, "r") as rf:
                diff_files = json.load(rf)
                scan_files = [path for path in diff_files if path.lower().endswith(want_suffix)]
        else:  # 未获取到环境变量,即全量扫描
            scan_files = [source_dir]

        # todo: 此处实现工具逻辑,输出结果,存放到result字典中
        # 设置配置文件、输出文件和结果文件
        rule_config_file = self.config(rules)
        error_output = "error_output.json"
        result=[]

        # 三端环境
        if sys.platform in ("darwin",):
            # 是否安装了PHP环境
            print("[debug] 查看php version")
            subProCPhp = subprocess.Popen(["php", "--version"])
            subProCPhp.wait()
            if subProCPhp.returncode != 0:
                print("[error] 机器没有安装php环境，请切换至Linux或Windows")
                return
            cmd = ["php"]
        elif sys.platform in ("linux", "linux2"):
            cmd = ["./php"]
        elif sys.platform in ("win32"):
            cmd = ["php.exe"]

        tool_bin = "PHP_CodeSniffer-3.6.0/bin/phpcs"
        cmd = cmd + [ 
            "-d",
            "memory_limit=\"-1\"",
            tool_bin,
            "--standard=%s" % rule_config_file,
            "--extensions=%s" % ','.join(want_suffix).replace('.', ''),
            "--report-json=%s" % error_output,
            "-v"
        ]

        # 正则过滤路径
        if re_exclude_path:
            cmd.append("--ignore=\"%s\"" % ','.join([path.replace(".*", "*") for path in re_exclude_path]))

        if not scan_files:
            print("[error] To-be-scanned files is empty")
            with open("result.json", "w") as fp:
                json.dump(result, fp, indent=2)
            return
        cmd.extend(scan_files)

        scan_cmd = " ".join(cmd)
        print("[debug] cmd: %s" % scan_cmd)
        # subprocess.call(cmd, stdout=subprocess.DEVNULL)
        subproc = subprocess.Popen(scan_cmd, 
                                    stdout=fs,
                                    shell=True)
        subproc.wait()
        # out, err = subproc.communicate()

        # 数据处理
        try:
            with open(error_output, "r") as f:
                outputs_data = json.load(f)
        except:
            print("[error] cannot load phpcs outputs: %s" % error_output)
            with open("result.json", "w") as resfp:
                json.dump(result, resfp, indent=2)
            return

        if 'files' in outputs_data:
            files_infos = outputs_data['files']
            for filePath, error_infos in files_infos.items():
                if 'messages' in error_infos:
                    for error in error_infos['messages']:
                        defect = {}
                        defect['path'] = filePath
                        defect['line'] = error['line']
                        defect['column'] = error['column']
                        defect['msg'] = error['message']
                        defect['rule'] = error['source']
                        defect['refs'] = []
                        if defect != {}:
                            result.append(defect)

        # 输出结果到指定的json文件
        with open("result.json", "w") as fp:
            json.dump(result, fp, indent=2)


if __name__ == '__main__':
    print("-- start run tool ...")
    PhpCs().run()
    print("-- end ...")