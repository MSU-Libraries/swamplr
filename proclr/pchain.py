import subprocess
import shlex

class PChain(object):
    AND = 0
    OR = 1
    PIPE = 2

    def __init__(self):
        self.procs = []
        self.s_out = ''
        self.s_err = ''

    def add(self, command, join=None):
        if (join is None):
            join = self.AND
        self.procs.append([command,join])

    def run(self):
        exit_code = None
        plist = []
        s_in = None

        for p in self.procs:
            cmd, join = p
            p_err = subprocess.PIPE
            if (join == self.PIPE):
                p_err = subprocess.STDOUT
            try:
                proc = subprocess.Popen( shlex.split(cmd), stdout=subprocess.PIPE, stderr=p_err, stdin=s_in )
                plist.append( proc )
            except:
                exit_code = 1
                break

            if join == self.PIPE:
                s_in = proc.stdout
            else:
                self.s_out, self.s_err = proc.communicate()
                exit_code = proc.returncode

                if (join == self.OR and exit_code == 0) or (join == self.AND and exit_code != 0):
                    break

        return exit_code

    def stdout(self):
        return self.s_out

    def stderr(self):
        return self.s_err

