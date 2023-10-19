$nuget = gcm nuget.exe -EA 0
if (-not $nuget) {
    $nuget = gcm .\nuget.exe -EA 0
    if (-not $nuget) {
        $ProgressPreference = "SilentlyContinue"
        iwr https://aka.ms/nugetclidl -o nuget.exe
        $nuget = gcm .\nuget.exe
    }
}

& $n install -o targets -x Microsoft.Windows.CppWinRT
& $n install -o targets -x Microsoft.WindowsAppSDK
& $n install -o targets -x Microsoft.Windows.ImplementationLibrary
