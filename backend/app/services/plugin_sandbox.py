"""Plugin sandbox for safe code execution.

Provides a restricted execution environment for untrusted plugin code.
Uses RestrictedPython for sandboxing Python code execution.
"""

import ast
import logging
from typing import Any, Callable

from ..models.plugin import PluginPermission

logger = logging.getLogger(__name__)


class SandboxError(Exception):
    """Raised when sandbox execution fails."""
    pass


class RestrictedGlobals:
    """Provides a restricted set of globals for sandboxed execution."""
    
    # Safe built-in functions
    SAFE_BUILTINS = {
        # Types
        "bool": bool,
        "int": int,
        "float": float,
        "str": str,
        "list": list,
        "dict": dict,
        "tuple": tuple,
        "set": set,
        "frozenset": frozenset,
        "bytes": bytes,
        "bytearray": bytearray,
        
        # Functions
        "len": len,
        "range": range,
        "enumerate": enumerate,
        "zip": zip,
        "map": map,
        "filter": filter,
        "sorted": sorted,
        "reversed": reversed,
        "min": min,
        "max": max,
        "sum": sum,
        "abs": abs,
        "round": round,
        "pow": pow,
        "divmod": divmod,
        "all": all,
        "any": any,
        "isinstance": isinstance,
        "issubclass": issubclass,
        "hasattr": hasattr,
        "getattr": getattr,
        "callable": callable,
        "repr": repr,
        "ascii": ascii,
        "chr": chr,
        "ord": ord,
        "hex": hex,
        "oct": oct,
        "bin": bin,
        "format": format,
        "hash": hash,
        "id": id,
        "type": type,
        "iter": iter,
        "next": next,
        "slice": slice,
        
        # Exceptions
        "Exception": Exception,
        "ValueError": ValueError,
        "TypeError": TypeError,
        "KeyError": KeyError,
        "IndexError": IndexError,
        "AttributeError": AttributeError,
        "RuntimeError": RuntimeError,
        "StopIteration": StopIteration,
        
        # Constants
        "True": True,
        "False": False,
        "None": None,
    }
    
    # Forbidden names that could be used for escape
    FORBIDDEN_NAMES = {
        "__import__",
        "__builtins__",
        "__class__",
        "__bases__",
        "__subclasses__",
        "__mro__",
        "__code__",
        "__globals__",
        "__closure__",
        "__func__",
        "__self__",
        "__dict__",
        "__module__",
        "__name__",
        "__qualname__",
        "eval",
        "exec",
        "compile",
        "open",
        "input",
        "breakpoint",
        "exit",
        "quit",
        "help",
        "credits",
        "license",
        "copyright",
    }
    
    @classmethod
    def get_safe_globals(cls, extra_globals: dict[str, Any] | None = None) -> dict[str, Any]:
        """Get a dictionary of safe globals for execution."""
        globals_dict = {"__builtins__": cls.SAFE_BUILTINS.copy()}
        
        if extra_globals:
            for name, value in extra_globals.items():
                if name not in cls.FORBIDDEN_NAMES:
                    globals_dict[name] = value
        
        return globals_dict


class CodeValidator:
    """Validates Python code for safety before execution."""
    
    FORBIDDEN_IMPORTS = {
        "os",
        "sys",
        "subprocess",
        "shutil",
        "pathlib",
        "socket",
        "urllib",
        "requests",
        "httpx",
        "aiohttp",
        "pickle",
        "marshal",
        "shelve",
        "ctypes",
        "multiprocessing",
        "threading",
        "asyncio",
        "importlib",
        "builtins",
        "__builtin__",
    }
    
    FORBIDDEN_ATTRIBUTES = {
        "__class__",
        "__bases__",
        "__subclasses__",
        "__mro__",
        "__code__",
        "__globals__",
        "__closure__",
        "__func__",
        "__self__",
    }
    
    def validate(self, code: str) -> tuple[bool, str | None]:
        """Validate code for safety.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Syntax error: {e}"
        
        for node in ast.walk(tree):
            # Check imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split(".")[0]
                    if module_name in self.FORBIDDEN_IMPORTS:
                        return False, f"Forbidden import: {alias.name}"
            
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_name = node.module.split(".")[0]
                    if module_name in self.FORBIDDEN_IMPORTS:
                        return False, f"Forbidden import: {node.module}"
            
            # Check attribute access
            elif isinstance(node, ast.Attribute):
                if node.attr in self.FORBIDDEN_ATTRIBUTES:
                    return False, f"Forbidden attribute access: {node.attr}"
            
            # Check function calls
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in RestrictedGlobals.FORBIDDEN_NAMES:
                        return False, f"Forbidden function call: {node.func.id}"
        
        return True, None


class PluginSandbox:
    """Sandboxed execution environment for plugin code."""
    
    def __init__(
        self,
        plugin_id: str,
        permissions: list[PluginPermission],
        timeout: float = 30.0,
    ):
        self._plugin_id = plugin_id
        self._permissions = set(permissions)
        self._timeout = timeout
        self._validator = CodeValidator()
        self._globals: dict[str, Any] = {}
        self._locals: dict[str, Any] = {}
    
    def _check_permission(self, permission: PluginPermission) -> None:
        """Check if the sandbox has a required permission."""
        if permission not in self._permissions:
            raise PermissionError(
                f"Plugin {self._plugin_id} does not have permission: {permission.value}"
            )
    
    def add_global(self, name: str, value: Any) -> None:
        """Add a value to the sandbox globals."""
        if name not in RestrictedGlobals.FORBIDDEN_NAMES:
            self._globals[name] = value
    
    def add_safe_module(self, name: str, module: Any, allowed_attrs: list[str]) -> None:
        """Add a module with only specific allowed attributes."""
        safe_module = type(name, (), {})()
        for attr in allowed_attrs:
            if hasattr(module, attr):
                setattr(safe_module, attr, getattr(module, attr))
        self._globals[name] = safe_module
    
    def execute(self, code: str) -> dict[str, Any]:
        """Execute code in the sandbox.
        
        Args:
            code: Python code to execute
            
        Returns:
            Dictionary of local variables after execution
            
        Raises:
            SandboxError: If code validation fails or execution errors
        """
        # Validate code
        is_valid, error = self._validator.validate(code)
        if not is_valid:
            raise SandboxError(f"Code validation failed: {error}")
        
        # Prepare execution environment
        exec_globals = RestrictedGlobals.get_safe_globals(self._globals)
        exec_locals: dict[str, Any] = {}
        
        try:
            # Compile and execute
            compiled = compile(code, f"<plugin:{self._plugin_id}>", "exec")
            exec(compiled, exec_globals, exec_locals)
            
            # Store locals for later access
            self._locals.update(exec_locals)
            
            return exec_locals
            
        except Exception as e:
            raise SandboxError(f"Execution error: {e}") from e
    
    def call_function(
        self,
        func_name: str,
        *args,
        **kwargs,
    ) -> Any:
        """Call a function defined in the sandbox.
        
        Args:
            func_name: Name of the function to call
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Function return value
            
        Raises:
            SandboxError: If function doesn't exist or execution fails
        """
        if func_name not in self._locals:
            raise SandboxError(f"Function not found: {func_name}")
        
        func = self._locals[func_name]
        if not callable(func):
            raise SandboxError(f"{func_name} is not callable")
        
        try:
            return func(*args, **kwargs)
        except Exception as e:
            raise SandboxError(f"Function execution error: {e}") from e
    
    def get_value(self, name: str) -> Any:
        """Get a value from the sandbox locals."""
        return self._locals.get(name)
    
    def reset(self) -> None:
        """Reset the sandbox state."""
        self._locals.clear()


class SafeMathModule:
    """Safe math module for sandbox use."""
    
    import math as _math
    
    # Safe math functions
    ceil = _math.ceil
    floor = _math.floor
    trunc = _math.trunc
    sqrt = _math.sqrt
    exp = _math.exp
    log = _math.log
    log10 = _math.log10
    log2 = _math.log2
    pow = _math.pow
    sin = _math.sin
    cos = _math.cos
    tan = _math.tan
    asin = _math.asin
    acos = _math.acos
    atan = _math.atan
    atan2 = _math.atan2
    sinh = _math.sinh
    cosh = _math.cosh
    tanh = _math.tanh
    degrees = _math.degrees
    radians = _math.radians
    factorial = _math.factorial
    gcd = _math.gcd
    isnan = _math.isnan
    isinf = _math.isinf
    isfinite = _math.isfinite
    
    # Constants
    pi = _math.pi
    e = _math.e
    tau = _math.tau
    inf = _math.inf
    nan = _math.nan


class SafeJsonModule:
    """Safe JSON module for sandbox use."""
    
    import json as _json
    
    @staticmethod
    def dumps(obj, **kwargs):
        """Serialize object to JSON string."""
        import json
        return json.dumps(obj, **kwargs)
    
    @staticmethod
    def loads(s, **kwargs):
        """Deserialize JSON string to object."""
        import json
        return json.loads(s, **kwargs)


class SafeReModule:
    """Safe regex module for sandbox use."""
    
    import re as _re
    
    @staticmethod
    def match(pattern, string, flags=0):
        import re
        return re.match(pattern, string, flags)
    
    @staticmethod
    def search(pattern, string, flags=0):
        import re
        return re.search(pattern, string, flags)
    
    @staticmethod
    def findall(pattern, string, flags=0):
        import re
        return re.findall(pattern, string, flags)
    
    @staticmethod
    def sub(pattern, repl, string, count=0, flags=0):
        import re
        return re.sub(pattern, repl, string, count, flags)
    
    @staticmethod
    def split(pattern, string, maxsplit=0, flags=0):
        import re
        return re.split(pattern, string, maxsplit, flags)
    
    @staticmethod
    def compile(pattern, flags=0):
        import re
        return re.compile(pattern, flags)
    
    # Flags
    IGNORECASE = _re.IGNORECASE
    MULTILINE = _re.MULTILINE
    DOTALL = _re.DOTALL


class SafeDatetimeModule:
    """Safe datetime module for sandbox use."""
    
    from datetime import datetime, date, time, timedelta, timezone
    
    datetime = datetime
    date = date
    time = time
    timedelta = timedelta
    timezone = timezone


def create_sandbox_with_safe_modules(
    plugin_id: str,
    permissions: list[PluginPermission],
) -> PluginSandbox:
    """Create a sandbox with safe standard library modules."""
    sandbox = PluginSandbox(plugin_id, permissions)
    
    # Add safe modules
    sandbox.add_global("math", SafeMathModule())
    sandbox.add_global("json", SafeJsonModule())
    sandbox.add_global("re", SafeReModule())
    sandbox.add_global("datetime", SafeDatetimeModule())
    
    return sandbox
