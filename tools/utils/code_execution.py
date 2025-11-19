# python_executor.py
# -*- coding: utf-8 -*-
"""Standalone Python execution helper.
Provides:
 - execute_python_code_sync(code, timeout) -> str (XML string)
 - execute_python_code_async(code, timeout) -> str (XML string)

XML format returned:
<result>
  <returncode>...</returncode>
  <timed_out>True|False</timed_out>
  <output>...escaped output...</output>
  <error>...escaped stderr...</error>
</result>
"""

import asyncio
import sys
import tempfile
import os
from typing import Optional
import uuid
import subprocess
from xml.sax.saxutils import escape as xml_escape


def _wrap_xml(
    returncode: Optional[int],
    stdout: Optional[str],
    stderr: Optional[str],
    timed_out: Optional[bool],
) -> str:
    """Wrap the results into an XML string, escaping text content."""
    output = ""

    if returncode is not None:
        output += f"<returncode>{str(returncode)}</returncode>\n"
    if timed_out is not None:
        output += f"<timed_out>{str(timed_out)}</timed_out>\n"
    if stdout is not None:
        output += f"<output>\n{xml_escape(stdout)}\n</output>\n"
    if stderr is not None:
        output += f"<error>\n{xml_escape(stderr)}\n</error>\n"

    return f"<result>\n{output}</result>"


def execute_python_code(code: str, timeout: float = 300.0) -> str:
    """
    Execute python code synchronously in a temporary file.
    Returns: XML-formatted string containing returncode, output, error, timed_out.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        filename = os.path.join(tmpdir, f"tmp_{uuid.uuid4().hex}.py")
        with open(filename, "w", encoding="utf-8") as f:
            f.write(code)

        timed_out = False
        try:
            completed = subprocess.run(
                [sys.executable, "-u", filename],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
                text=True,
            )
            returncode = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            # subprocess.TimeoutExpired may have partial output depending on platform
            stdout = (
                exc.stdout.decode("utf-8", errors="replace")
                if isinstance(exc.stdout, (bytes, bytearray))
                else ""
            )
            stderr = (
                exc.stderr.decode("utf-8", errors="replace")
                if isinstance(exc.stderr, (bytes, bytearray))
                else ""
            )
            tm_msg = f"\nTimeoutError: execution exceeded timeout of {timeout} seconds."
            if tm_msg.strip() not in stderr:
                stderr = stderr + tm_msg
            returncode = -1

        return _wrap_xml(returncode, stdout, stderr, timed_out)

# Example usage when run as a script
if __name__ == "__main__":
    sample_code = 'print("Hello from sandboxed runner")\nimport sys\nprint("stderr example", file=sys.stderr)\n'
    print("Synchronous run result:")
    print(execute_python_code(sample_code, timeout=5.0))
