from .. import log
from .tube import tube
import subprocess, fcntl, os

class process(tube):
    def __init__(self, args, shell = False, executable = None, env = None,
                 timeout = 'default', log_level = log.INFO):
        super(process, self).__init__(timeout, log_level)

        if executable:
            self.program = executable
        elif isinstance(args, (str, unicode)):
            self.program = args
        elif isinstance(args, (list, tuple)):
            self.program = args[0]
        else:
            log.error("process(): Do not understand the arguments %s" % repr(args))

        self.proc = subprocess.Popen(
            args, shell = shell, executable = executable, env = env,
            stdin = subprocess.PIPE, stdout = subprocess.PIPE,
            stderr = subprocess.STDOUT)
        self.stop_noticed = False

        # Set in non-blocking mode so that a call to call recv(1000) will
        # return as soon as a the first byte is available
        fd = self.proc.stdout.fileno()
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

        log.success("Started program %s" % repr(self.program))

    def kill(self):
        """kill()

        Kills the process.
        """

        self.close()

    def shutdown(self, direction = "out"):
        """shutdown(direction = "out")

        Closes one of the file descriptors to the process.

        Args:
          direction(str): Either the string "in" or "out".
        """

        if direction == "out":
            self.proc.stdin.close()

        if direction == "in":
            self.proc.stdout.close()

        if False not in [self.proc.stdin.closed, self.proc.stdout.closed]:
            self.close()

    def poll(self):
        """poll() -> int

        Poll the exit code of the process. Will return None, if the
        process has not yet finished and the exit code otherwise.
        """

        poll = self.proc.poll()
        if poll != None and not self.stop_noticed:
            self.stop_noticed = True
            log.info("Program %s stopped with exit code %d" % (repr(self.program), poll))

        return poll

    def communicate(self, stdin = None):
        """communicate(stdin = None) -> str

        Calls :meth:`subprocess.Popen.communicate` method on the process.
        """

        return self.proc.communicate(stdin)

    # Implementation of the methods required for tube
    def recv_raw(self, numb):
        # This is a slight hack. We try to notice if the process is
        # dead, so we can write a message.
        self.poll()

        if self.proc.stdout.closed:
            raise EOFError

        if not self.can_recv_raw(self.timeout):
            return None

        # This will only be reached if we either have data,
        # or we have reached an EOF. In either case, it
        # should be safe to read without expecting it to block.
        data = self.proc.stdout.read(numb)

        if data == '':
            self.proc.stdout.close()
            raise EOFError
        else:
            return data

    def send_raw(self, data):
        # This is a slight hack. We try to notice if the process is
        # dead, so we can write a message.
        self.poll()

        if self.proc.stdin.closed:
            raise EOFError

        try:
            self.proc.stdin.write(data)
            self.proc.stdin.flush()
        except IOError as e:
            raise EOFError

    def settimeout_raw(self, timeout):
        pass

    def can_recv_raw(self, timeout):
        import select
        if timeout == None:
            return select.select([self.proc.stdout], [], []) == ([self.proc.stdout], [], [])
        else:
            return select.select([self.proc.stdout], [], [], timeout) == ([self.proc.stdout], [], [])

    def connected(self):
        return self.poll() == None

    def close(self):
        # First check if we are already dead
        self.poll()

        if self.stop_noticed:
            try:
                self.proc.kill()
                self.stop_noticed = True
                log.info('Stopped program %s' % repr(self.target))
            except OSError as e:
                pass


    def fileno(self):
        if not self.connected():
            log.error("A stopped program does not have a file number")

        return self.proc.stdout.fileno()
