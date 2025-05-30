# azure-cli

This sample project uses DLL packing, wheel dependencies and entrypoint
to create a single package containing the entire Azure CLI tool.

```powershell
$> python -m venv .env
$> .env\Scripts\activate
(.env)> pip install -r requirements-win32.txt
(.env)> python -m pymsbuild
(.env)> .\azure-cli\az.exe ...
```

*Want more details? Ask on the issue tracker.*
