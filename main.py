#!/usr/bin/env python
import datetime
import json
import re
import socket

# =================== GLOBALS ================================

DEBUG = False

config_file = ""
settings_vars = dict()
user_vars = dict()
menuentry_vars = dict()
set_vars = dict()
insmod_vars = dict()
search_vars = dict()
kernel_vars = dict()
initramfs_vars = dict()

# magic variables always return a function as they are python function calls, just ones we determine
hostname = socket.gethostname()

magic_vars = {
    "date": lambda x: datetime.datetime.now().strftime(x),
    "hostname": lambda x: hostname if len(x) <= 0 else x.strip().replace(' ', '-').format(host=hostname)
}

# Regex for checking the variables in strings
vc_regex = re.compile(r"{(\w.+)}")

NS_VAR = "__pykernel__"
NS = globals()[NS_VAR] = { }


def pop_entry_or_exit(key: str, target_dict: dict):
    if target_dict.get(key):
        return target_dict.pop(key)
    else:
        print(f"{key} doesn't exist in {target_dict}")
        exit(1)


def add_config_entry_to_global(**setting_dict: [dict, list]):
    global NS, magic_vars

    for key, var in setting_dict.items():
        if key not in NS and key not in magic_vars:
            if isinstance(var, str):
                NS[key] = var.format(**NS)
            else:
                NS[key] = var


def parse_strings(input_dict, **keys):
    global NS, magic_vars

    output_dict = {}
    for k, v in input_dict.items():
        if k in magic_vars:
            # If a magic var exists in the string, add it to our global so everyone can access it
            output_dict.update({k: magic_vars[k](v)})
        else:
            output_dict.update({k: v.format(**keys) if isinstance(v, str) else v})

    return output_dict


# ===============================================================

# ===================== OPEN FILE ===============================


try:
    with open("config.json", "r", ) as cjson:
        config_file = cjson.read()
        config_file = json.loads(config_file)

except FileNotFoundError as e:
    print(e)
    exit(1)

# ===============================================================


# Pop all the entries we need from the config file into their variables
# ===============================================================

# ==================== NS ======================================
NS = pop_entry_or_exit("settings", config_file)
NS = parse_strings(NS, **NS)

NS.update(pop_entry_or_exit("vars", NS))
NS = parse_strings(NS, **NS)
# ===============================================================
# ==================== MENUENTRY ================================
menuentry_vars = pop_entry_or_exit("menuentry", config_file)
menuentry_vars = parse_strings(menuentry_vars, **NS)

if menuentry_vars.get("class"):
    tmp = ""
    for i in menuentry_vars["class"]:
        tmp = tmp + f"--class {i} ".format(**NS)
    menuentry_vars["class"] = tmp.strip()
# ===============================================================


# ==================== SET ======================================
set_vars = pop_entry_or_exit("set", config_file)
set_vars = parse_strings(set_vars, **NS)

if len(set_vars) > 0:
    tmp = ""
    for k, v in set_vars.items():
        tmp += f"{k}={v}"

    set_vars = tmp.format(**NS)
# ================================================================


# ==================== INSMOD ====================================
insmod_vars = pop_entry_or_exit("insmod", config_file)
insmod_string = ""
for key in insmod_vars:
    insmod_string = insmod_string + f"\tinsmod {key}\n\r"
insmod_vars = insmod_string.format(**NS)
# ================================================================


# ==================== SEARCH ====================================
search_vars = pop_entry_or_exit("search", config_file)
search_vars = parse_strings(search_vars, **NS)

search_string = "   search "
for key, val in search_vars.items():
    search_string += f"{key.strip()}{'=' if len(val) >= 1 else ''}{val} "
search_vars = search_string.format(**NS)

# ================================================================

# ==================== KERNEL ====================================
kernel_vars = pop_entry_or_exit("kernel", config_file)
kernel_vars = parse_strings(kernel_vars, **NS)
kernel_string = ""

if kernel_vars.get("title"):
    kernel_title = kernel_vars.get("title")
    kernel_string += f"echo \"{kernel_title}\"".format(**NS)
    kernel_string += "\n\r"

if kernel_vars.get("linux"):
    initramfs_boot_file = kernel_vars["linux"]
    kernel_string += f"\tlinux {initramfs_boot_file}".format(**NS)

if kernel_vars.get("options"):
    for key, val in kernel_vars["options"].items():
        kernel_string += f" {key.strip()}{'=' if len(val) >= 1 else ''}{val}".format(**NS)

kernel_vars = kernel_string
# ================================================================

# ==================== INITRAMFS =================================
initramfs_vars = pop_entry_or_exit("initramfs", config_file)
initramfs_vars = parse_strings(initramfs_vars, **NS)
initramfs_string = ""

if initramfs_vars.get("title"):
    initramfs_title = initramfs_vars.get("title")
    initramfs_string += f"echo \"{initramfs_title}\"".format(**NS)
    initramfs_string += "\n\r"

if initramfs_vars.get("initrd"):
    initramfs_boot_file = initramfs_vars["initrd"]
    initramfs_string += f"\tinitrd {initramfs_boot_file}".format(**NS)

if initramfs_vars.get("options"):
    for key, val in initramfs_vars["options"].items():
        initramfs_string += f"{key.strip()}{'=' if len(val) >= 1 else ''}{val}".format(**NS)

initramfs_vars = initramfs_string
# ================================================================

# ================================================================


template_string = '''
#!/bin/sh
exec tail -n +3 $0
# This file provides an easy way to add custom menu entries.  Simply type the
# menu entries you want to add after this comment.  Be careful not to change
# the 'exec tail' line above.


'''

template_string += "menuentry '{title}' {class} {id} {{\n\r".format(**menuentry_vars)
template_string += "\tload video\n\r\t"
template_string += set_vars +"\n\r"
template_string += insmod_vars+"\n\r\t"
template_string += search_vars+"\n\r\t"
template_string += kernel_vars+"\n\r\t"
template_string += initramfs_vars+"\n\r"
template_string += "}"

print(template_string)