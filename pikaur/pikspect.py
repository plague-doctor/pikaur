import sys
import subprocess
import tty
import pty
import gettext
import io
import termios
import select
import shutil
import struct
import fcntl
import uuid
import os
import multiprocessing
from multiprocessing.pool import ThreadPool
from time import sleep
from typing import List, Tuple, Dict

from .core import DataType
from .pprint import bold_line, PrintLock, print_stdout
from .threading import handle_exception_in_thread, ThreadSafeBytesStorage


PACMAN_TRANSLATION = gettext.translation('pacman', fallback=True)


def _p(msg: str) -> str:
    return PACMAN_TRANSLATION.gettext(msg)


Y = _p("Y")
N = _p("N")


DEFAULT_QUESTIONS: Dict[str, List[str]] = {
    Y: [
        bold_line(" {} {} ".format(message, _p('[Y/n]')))
        for message in [
            _p('Proceed with installation?'),
            _p('Do you want to remove these packages?'),
        ]
    ],
    N: [],
}


SMALL_TIMEOUT = 0.1


class TTYRestore():

    old_tcattrs = None

    @classmethod
    def save(cls):
        if sys.stdin.isatty():
            cls.old_tcattrs = termios.tcgetattr(sys.stdin.fileno())

    @classmethod
    def restore(cls, *_whatever):
        if sys.stderr.isatty():
            termios.tcdrain(sys.stderr.fileno())
        if sys.stdout.isatty():
            termios.tcdrain(sys.stdout.fileno())
        if sys.stdin.isatty():
            termios.tcflush(sys.stdin.fileno(), termios.TCIOFLUSH)
        if cls.old_tcattrs:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, cls.old_tcattrs)


TTYRestore.save()


class PikspectPopen(subprocess.Popen):

    saved_bytes: bytes


class PikspectTaskData(DataType):
    proc: PikspectPopen
    pty_out: io.BytesIO
    pty_in: io.TextIOWrapper
    default_questions: Dict[str, Tuple[str]]
    print_output: bool
    save_output: bool
    task_id: uuid.UUID


@handle_exception_in_thread
def cmd_output_handler(task_data: PikspectTaskData) -> None:
    historic_output: List[bytes] = []
    max_question_length = max([
        len(q)
        for answer, questions in task_data.default_questions.items()
        for q in questions
    ]) + 10
    default_questions_bytes: Dict[str, List[List[bytes]]] = {
        answer: [
            [chr(char).encode('utf-8') for char in question.encode('utf-8')]
            for question in questions
        ]
        for answer, questions in task_data.default_questions.items()
    }
    while True:
        # if proc.returncode is not None:
            # break
        output = task_data.pty_out.read(1)
        if not output:
            break
        historic_output = historic_output[-max_question_length:] + [output, ]

        if task_data.print_output:
            with PrintLock():
                sys.stdout.buffer.write(output)
                sys.stdout.buffer.flush()
        if task_data.save_output:
            ThreadSafeBytesStorage.add_bytes(task_data.task_id, output)
        for answer, questions in default_questions_bytes.items():
            for question in questions:
                if len(historic_output) < len(question) or (
                        historic_output[-len(question):] != question
                ):
                    continue
                if task_data.print_output:
                    print_stdout(answer + '\n')
                with PrintLock():
                    if task_data.save_output:
                        ThreadSafeBytesStorage.add_bytes(
                            task_data.task_id, answer.encode('utf-8') + b'\n'
                        )
                    task_data.pty_in.write(answer)
                    sleep(SMALL_TIMEOUT)
                    task_data.pty_in.write('\n')
                historic_output = []
                break


@handle_exception_in_thread
def user_input_reader(task_data: PikspectTaskData) -> None:
    while True:
        if task_data.proc.returncode is not None:
            break
        char = None

        while sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
            line = sys.stdin.read(1)
            if line:
                char = line
                break
            else:
                return
        else:
            sleep(SMALL_TIMEOUT)
            continue

        try:
            with PrintLock():
                task_data.pty_in.write(char)
        except ValueError:
            return
        if task_data.print_output:
            print_stdout(char)
        if task_data.save_output:
            ThreadSafeBytesStorage.add_bytes(task_data.task_id, char.encode('utf-8'))


@handle_exception_in_thread
def communicator(task_data: PikspectTaskData) -> None:
    # @TODO: wip #161
    # task_data.proc.communicate()
    task_data.proc.wait()


def set_terminal_geometry(file_descriptor: int, rows: int, columns: int) -> None:
    term_geometry_struct = struct.pack("HHHH", rows, columns, 0, 0)
    fcntl.ioctl(file_descriptor, termios.TIOCSWINSZ, term_geometry_struct)


class NestedTerminal():

    def __enter__(self) -> os.terminal_size:
        real_term_geometry = shutil.get_terminal_size((80, 80))
        if sys.stdin.isatty():
            tty.setcbreak(sys.stdin.fileno())
        if sys.stderr.isatty():
            tty.setcbreak(sys.stderr.fileno())
        if sys.stdout.isatty():
            tty.setcbreak(sys.stdout.fileno())
        return real_term_geometry

    def __exit__(self, *exc_details) -> None:
        TTYRestore.restore()


# pylint: disable=too-many-locals,too-many-arguments
def pikspect(
        cmd: List[str],
        print_output=True,
        save_output=True,
        default_questions: Dict[str, List[str]] = None,
        conflicts: List[List[str]] = None,
        accepted_replacements: List[List[str]] = None,
        declined_replacements: List[List[str]] = None,
        **kwargs
) -> PikspectPopen:

    if not default_questions:
        default_questions = {}
        default_questions.update(DEFAULT_QUESTIONS)

    extra_questions: Dict[str, List[str]] = {Y: [], N: []}

    if conflicts:
        extra_questions[Y] += [
            bold_line(" {} {} ".format(message, _p('[y/N]')))
            for message in [
                _p('%s and %s are in conflict. Remove %s?') % (new_pkg, old_pkg, old_pkg)
                for new_pkg, old_pkg in conflicts
            ]
        ]

    for answer, replacements in (
            (Y, accepted_replacements),
            (N, declined_replacements),
    ):
        if not replacements:
            continue
        extra_questions[answer] += [
            bold_line(" {} {} ".format(message, _p('[Y/n]')))
            for message in [
                _p('Replace %s with %s/%s?') % (old_pkg, new_pkg_repo, new_pkg)
                for new_pkg, new_pkg_repo, old_pkg in replacements
            ]
        ]

    for answer in (Y, N):
        if extra_questions[answer]:
            default_questions[answer] = default_questions[answer] + extra_questions[answer]

    task_id = uuid.uuid4()

    with NestedTerminal() as real_term_geometry:
        pty_user_master, pty_user_slave = pty.openpty()
        pty_cmd_master, pty_cmd_slave = pty.openpty()
        pty_out = open(pty_cmd_master, 'rb')
        set_terminal_geometry(
            pty_out.fileno(),
            columns=real_term_geometry.columns,
            rows=real_term_geometry.lines
        )

        if 'sudo' in cmd:
            subprocess.run(['sudo', '-v'])
        proc = PikspectPopen(
            cmd,
            stdin=pty_user_slave,
            stdout=pty_cmd_slave,
            stderr=pty_cmd_slave,
            **kwargs
        )
        with open(pty_user_master, 'w') as pty_in:
            task_data = PikspectTaskData(
                proc=proc,
                pty_out=pty_out,
                pty_in=pty_in,
                default_questions=default_questions,
                print_output=print_output,
                save_output=save_output,
                task_id=task_id
            )
            with ThreadPool(processes=3) as pool:
                output_task = pool.apply_async(cmd_output_handler, (task_data, ))
                pool.apply_async(user_input_reader, (task_data, ))
                communicate_task = pool.apply_async(communicator, (task_data, ))

                pool.close()
                communicate_task.get()
                try:
                    output_task.get(timeout=SMALL_TIMEOUT)
                except multiprocessing.context.TimeoutError:
                    pass
                pool.terminate()

    if save_output:
        proc.saved_bytes = ThreadSafeBytesStorage.get_bytes_output(task_id)
    return proc


if __name__ == "__main__":
    pikspect(
        [
            'sudo',
            'pacman',
        ] + sys.argv[1:],
    )
