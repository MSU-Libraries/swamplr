import os
import sys
import argparse
from ConfigParser import ConfigParser
import pymysql
from datetime import datetime

def build_cache():
    parser = argparse.ArgumentParser()
    parser.add_argument('config', metavar='CONFIG', help='Absolute path to the config to be used',
                        default="/var/www/swamplr/swamplr.cfg")
    pargs = parser.parse_args()
    configs = load_configs(pargs.config)
    path_to_object_store = configs.get("fedora", "OBJECT_STORE",
                                       vars={"OBJECT_STORE": "/usr/local/fedora/data/objectStore"})
    database = dict(configs.items("database.default")) 
    
    connection = pymysql.connect(host=database["HOST"],
                                user=database["USER"],
                                password=database["PASSWORD"],
                                db=database["NAME"],
                                charset="utf8mb4",
                                cursorclass=pymysql.cursors.DictCursor)

    with connection.cursor() as cursor:
        sql = "SELECT * FROM `swamplr_namespaces_cache_job`"
        cursor.execute(sql)
        result = cursor.fetchone()
        process_id = result["process_id"] if result else 0
        running = is_running(process_id)   
    
    if running:
        print "Cache job currently running with pid: {0}".format(process_id)
        
    else:
        current_process = os.getgid()
        with connection.cursor() as cursor:
            if result:            
                sql = "UPDATE `swamplr_namespaces_cache_job` SET process_id = %s WHERE process_id = {0}".format(process_id)
            else:
                sql = "INSERT INTO `swamplr_namespaces_cache_job` (`process_id`) VALUES (%s)"
 
            cursor.execute(sql, (current_process, ))
            
        ns_count = count_namespaces(path_to_object_store)    
        
        with connection.cursor() as cursor: 
            # This method performs a delete and replace (not an update) if the row already exists.
            # Therefore all columns should be supplied in the replace statement.
            sql = "INSERT INTO `swamplr_namespaces_namespace_cache` (`namespace`, `count`) VALUES (%s, %s)\
                  ON DUPLICATE KEY UPDATE `count` = VALUES(count)"
            cursor.executemany(sql, ns_count.items())
            
            time = datetime.now()
            sql = "UPDATE `swamplr_namespaces_cache_job` SET process_id = 0, last_run = '{0}' WHERE process_id = '{1}'".format(time, current_process)
            cursor.execute(sql)

        connection.commit()
        connection.close()
        print "Job Complete at {0}".format(time)
        print "Updated {0} namespace rows".format(len(ns_count))

def is_running(pid):
    """Check if process given pid is running."""
    running = False
    if pid != 0:
        try:
            os.kill(pid, 0)
            running = True
        except:
            pass
    return running

def count_namespaces(path):
    """Count namespaces via the Fedora Commons object store."""
    ns_count = {}
    for hexdir in os.listdir(path):
        hexpath = os.path.join(path, hexdir)
        if os.path.isdir(hexpath):
            for objectdir in os.listdir(hexpath):
                fedora_and_namespace = objectdir.split("%3A")[1]
                namespace = fedora_and_namespace.split("%2F")[1]
                ns_count[namespace] = ns_count.get(namespace, 0) + 1                
    return ns_count

def load_configs(path_to_configs):
    """Load configs from default location."""
    configs = ConfigParser()
    # Load configs preserving case
    configs.optionxform = str
    # Individual configs accessed via configs object.
    configs.readfp(open(path_to_configs))
    return configs



if __name__ == "__main__":
    build_cache()
