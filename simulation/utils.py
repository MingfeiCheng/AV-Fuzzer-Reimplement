import os
import shutil
import time

from loguru import logger

def check_rename_record(default_path, target_path, case_id):
    if not os.path.exists(target_path):
        os.makedirs(target_path)

    folders = os.listdir(default_path)
    folders = sorted(folders)
    if len(folders) > 0:
        original_folder = folders[-1]
        original_fpath = os.path.join(default_path, original_folder)
        target_fpath = os.path.join(target_path, case_id)
        shutil.move(original_fpath, target_fpath)
        logger.info(' --- Move: ' + original_fpath + ' ==> ' + target_fpath)

def enable_modules(dv, modules):
    # try 5 times
    not_all = True
    while not_all:
        not_all = False
        module_status = dv.get_module_status()
        for module, status in module_status.items():
            if (not status) and (module in modules):
                dv.enable_module(module)
                not_all = True
        time.sleep(1)

def disnable_modules(dv, modules):
    not_all = True
    while not_all:
        not_all = False
        module_status = dv.get_module_status()
        for module, status in module_status.items():
            if status and (module in modules):
                dv.disable_module(module)
                not_all = True
        time.sleep(1)
