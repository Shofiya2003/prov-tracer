import io
import os
import sys
import tempfile
import subprocess
import typing_extensions
import tarfile
import pathlib
import typer
import shutil
import rich
from probe_py.generated.parser import parse_probe_log
import analysis
import util
import traceback

rich.traceback.install(show_locals=False)


project_root = pathlib.Path(__file__).resolve().parent.parent

A = typing_extensions.Annotated

app = typer.Typer()

def transcribe(probe_dir: pathlib.Path, output: pathlib.Path, debug: bool = False) -> None:
    """
    Transcribe the recorded data from PROBE_DIR into OUTPUT.
    """
    probe_log_tar_obj = tarfile.open(name=str(output), mode="x:gz")
    probe_log_tar_obj.add(probe_dir, arcname="")
    probe_log_tar_obj.addfile(
        util.default_tarinfo("README"),
        fileobj=io.BytesIO(b"This archive was generated by PROBE."),
    )
    probe_log_tar_obj.close()
    if debug:
        print()
        print("PROBE log files:")
        for path in probe_dir.glob("**/*"):
            if not path.is_dir():
                print(path, path.stat().st_size)
        print()
    shutil.rmtree(probe_dir)

@app.command()    
def transcribe_only(
        input_dir: pathlib.Path,
        output: pathlib.Path = pathlib.Path("probe_log"),
        debug: bool = typer.Option(default=False, help="Run in verbose mode"),
) -> None:
    """
    Transcribe the recorded data from INPUT_DIR into OUTPUT.
    """
    transcribe(input_dir, output, debug)

@app.command(
    context_settings=dict(
        ignore_unknown_options=True,
    ),
)
def record(
        cmd: list[str],
        gdb: bool = typer.Option(default=False, help="Run in GDB"),
        debug: bool = typer.Option(default=False, help="Run verbose & debug build of libprobe"),
        make: bool = typer.Option(default=False, help="Run make prior to executing"),
        output: pathlib.Path = pathlib.Path("probe_log"),
        no_transcribe: bool = typer.Option(default=False, help="Only execute without transcribing"),
) -> None:
    """
    Execute CMD... and optionally record its provenance into OUTPUT.
    """
    if make:
        proc = subprocess.run(
            ["make", "--directory", str(project_root / "libprobe"), "all"],
        )
        if proc.returncode != 0:
            typer.secho("Make failed", fg=typer.colors.RED)
            raise typer.Abort()
    if output.exists():
        output.unlink()
    libprobe = project_root / "libprobe/build" / ("libprobe-dbg.so" if debug or gdb else "libprobe.so")
    if not libprobe.exists():
        typer.secho(f"Libprobe not found at {libprobe}", fg=typer.colors.RED)
        raise typer.Abort()
    ld_preload = str(libprobe) + (":" + os.environ["LD_PRELOAD"] if "LD_PRELOAD" in os.environ else "")
    probe_dir = pathlib.Path(tempfile.mkdtemp(prefix=f"probe_log_{os.getpid()}"))
    if gdb:
        subprocess.run(
            ["gdb", "--args", "env", f"__PROBE_DIR={probe_dir}", f"LD_PRELOAD={ld_preload}", *cmd],
        )
    else:
        if debug:
            typer.secho(f"Running {cmd} with libprobe into {probe_dir}", fg=typer.colors.GREEN)
        proc = subprocess.run(
            cmd,
            env={**os.environ, "LD_PRELOAD": ld_preload, "__PROBE_DIR": str(probe_dir)},
        )

        if no_transcribe:
            typer.secho(f"Temporary probe directory: {probe_dir}", fg=typer.colors.YELLOW)
            raise typer.Exit(proc.returncode)
        
        transcribe(probe_dir, output, debug)
        raise typer.Exit(proc.returncode)

@app.command()
def process_graph(
        input: pathlib.Path = pathlib.Path("probe_log"),
) -> None:
    """
    Write a process graph from PROBE_LOG in DOT/graphviz format.
    """
    if not input.exists():
        typer.secho(f"INPUT {input} does not exist\nUse `PROBE record --output {input} CMD...` to rectify", fg=typer.colors.RED)
        raise typer.Abort()
    prov_log = parse_probe_log(input)
    console = rich.console.Console(file=sys.stderr)
    process_graph = analysis.provlog_to_digraph(prov_log)
    for warning in analysis.validate_provlog(prov_log):
        console.print(warning, style="red")
    rich.traceback.install(show_locals=False) # Figure out why we need this
    process_graph = analysis.provlog_to_digraph(prov_log)
    for warning in analysis.validate_hb_graph(prov_log, process_graph):
        console.print(warning, style="red")
    print(analysis.digraph_to_pydot_string(prov_log, process_graph))
    

@app.command()
def dump(
        input: pathlib.Path = pathlib.Path("probe_log"),
) -> None:
    """
    Write the data from PROBE_LOG in a human-readable manner.
    """
    if not input.exists():
        typer.secho(f"INPUT {input} does not exist\nUse `PROBE record --output {input} CMD...` to rectify", fg=typer.colors.RED)
        raise typer.Abort()
    processes_prov_log = parse_probe_log(input)
    for pid, process in processes_prov_log.processes.items():
        print(pid)
        for exid, exec_epoch in process.exec_epochs.items():
            print(pid, exid)
            for tid, thread in exec_epoch.threads.items():
                print(pid, exid, tid)
                for op_no, op in enumerate(thread.ops):
                    print(pid, exid, tid, op_no, op.data)
                print()


# scp source destination
# find the <device>-<inode>.prov on source
# upload to destination
# find <device>-<inode>.prov inode on source
# augment to InodeHistory
# transfer the file to destination

# scp Desktop/sample_example.txt root@136.183.142.28:/home/remote_dir 
@app.command()
def scp(
        cmd: list[str],
        port: str = typer.Option(22, "--p", "-P")
) -> None:
    """
    """
    try:
    # iterate from the end 
        destination = cmd[-1]
        source = cmd[-2]

        # source is local and destination is remote
        if "@" not in source:
            user_name_and_ip = destination.split(":")[0]
            destination_path = destination.split(":")[1]
            local_file_path = source
            src_inode, src_device = get_inode_and_device_on_local(local_file_path)
            cmd.insert(0,f"-P {port}")
            cmd.insert(0,"scp")
            upload_files(cmd)
            remote_file_path = os.path.join(destination_path, os.path.basename(local_file_path))
            get_inode_and_device_on_remote(remote_file_path, user_name_and_ip)
        # source is remote and destination is local
        elif "@" not in destination:
            user_name_and_ip = source.split(":")[0]
            source_file_path = source.split(":")[1]
            destination_path = destination
            get_inode_and_device_on_remote(source_file_path, user_name_and_ip)
            cmd.insert(0,f"-P {port}")
            cmd.insert(0,"scp")
            upload_files(cmd)
            destination_path = os.path.join(destination_path, os.path.basename(source_file_path))
            print(destination_path)
            get_inode_and_device_on_local(destination_path)
        else:
            user_name_and_ip_src = source.split(":")[0]
            source_file_path = source.split(":")[1]
            get_inode_and_device_on_remote(source_file_path, user_name_and_ip_src)
            cmd.insert(0,f"-P {port}")
            cmd.insert(0,"scp")
            upload_files(cmd)
            user_name_and_ip_dest = destination.split(":")[0]
            remote_file_path = os.path.join(destination_path, os.path.basename(source_file_path))
            destination_path = destination.split(":")[1]
            get_inode_and_device_on_remote(remote_file_path, user_name_and_ip_dest)


    except Exception as e:
        print(str(e))



@app.command()
def rsync(
        cmd: list[str],
        port: str = typer.Option(22, "--p", "-P"),
        dry_run: bool = typer.Option(False, "--dry-run", help="Simulate the file transfer.")
) -> None:
    """
    Transfer files using rsync and get inode and device numbers.
    """
    try:
        # Iterate from the end
        destination = cmd[-1]
        source = cmd[-2]

        # Source is local and destination is remote
        if "@" not in source:
            user_name_and_ip = destination.split(":")[0]
            destination_path = destination.split(":")[1]
            local_file_path = source
            src_inode, src_device = get_inode_and_device_on_local(local_file_path)
            cmd.insert(0, f"--rsh=ssh -p {port}")
            cmd.insert(0, "rsync")
            if dry_run:
                cmd.append("--dry-run")
            run_rsync(cmd)
            if not dry_run:
                remote_file_path = os.path.join(destination_path, os.path.basename(local_file_path))
                get_inode_and_device_on_remote(remote_file_path, user_name_and_ip)
        # Source is remote and destination is local
        elif "@" not in destination:
            user_name_and_ip = source.split(":")[0]
            source_file_path = source.split(":")[1]
            destination_path = destination
            if dry_run:
                cmd.append("--dry-run")
            run_rsync(cmd)
            if not dry_run:
                get_inode_and_device_on_remote(source_file_path, user_name_and_ip)
                destination_path = os.path.join(destination_path, os.path.basename(source_file_path))
                get_inode_and_device_on_local(destination_path)
        else:
            user_name_and_ip_src = source.split(":")[0]
            source_file_path = source.split(":")[1]
            if dry_run:
                cmd.append("--dry-run")
            run_rsync(cmd)
            if not dry_run:
                get_inode_and_device_on_remote(source_file_path, user_name_and_ip_src)
                user_name_and_ip_dest = destination.split(":")[0]
                destination_path = destination.split(":")[1]
                remote_file_path = os.path.join(destination_path, os.path.basename(source_file_path))
                get_inode_and_device_on_remote(remote_file_path, user_name_and_ip_dest)
    except Exception as e:
        print(str(e))

def run_rsync(cmd):
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result)
        if "--dry-run" in cmd:
            typer.echo("Dry run completed. These files would be transferred:")
            typer.echo(result.stdout)
        else:
            typer.echo("File transfer successful.")
            typer.echo(result.stdout)
    except subprocess.CalledProcessError as e:
        # Capture and print the error message
        typer.echo(f"Error occurred during file transfer: {e}")
        typer.echo(f"Exit code: {e.returncode}")
        typer.echo(f"Error output: {e.stderr}")



def upload_files(cmd):
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result)
        typer.echo("File transfer successful.")
        typer.echo(result.stdout)
    except subprocess.CalledProcessError as e:
        # Capture and print the error message
        typer.echo(f"Error occurred during file transfer: {e}")
        typer.echo(f"Exit code: {e.returncode}")
        typer.echo(f"Error output: {e.stderr}")

def get_inode_and_device_on_remote(remote_file_path, user_name_and_ip):
    try:
        # Get the remote file path
        
        print(remote_file_path)
        # SSH command to get inode and device number
        ssh_command = f"ssh -p 2222 {user_name_and_ip} 'stat -c \"%d %i\" {remote_file_path}'"
        result = subprocess.run(ssh_command, shell=True, check=True, capture_output=True, text=True)
        # Parse the result
        device, inode = result.stdout.strip().split()
        print(device, " ", inode)
    except subprocess.CalledProcessError as e:
        # Capture and print the error message
        typer.echo(f"Error occurred during file transfer: {e}")
        typer.echo(f"Exit code: {e.returncode}")
        typer.echo(f"Error output: {e.stderr}")
    
def get_inode_and_device_on_local(file_path):
    try:
        print(file_path)
        file_stat = os.stat(file_path)
        device = file_stat.st_dev
        inode = file_stat.st_ino
        print(device, " ", inode)
        return inode, device
    except FileNotFoundError:
        raise Exception(f"File not found: {file_path}")
    except Exception as e:
        raise Exception(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    app()
