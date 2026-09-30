import asyncio, os
from . import tool

@tool("shell.run", "Run a shell command on the host.",
      {"type": "object", "properties": {"cmd": {"type":"string"}, "cwd": {"type":"string"},
                                        "timeout": {"type":"integer","default":120}},
       "required": ["cmd"]}, danger="high")
async def shell_run(cmd, cwd=None, timeout=120):
    proc = await asyncio.create_subprocess_shell(cmd, cwd=cwd or os.getcwd(),
                                                  stdout=asyncio.subprocess.PIPE,
                                                  stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill(); return {"ok": False, "error": "timeout"}
    return {"ok": proc.returncode == 0, "code": proc.returncode,
            "stdout": out.decode(errors="ignore")[:8000],
            "stderr": err.decode(errors="ignore")[:4000]}
