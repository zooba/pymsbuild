import os, sys
EXPECT_PREFIX = os.getenv("BUILD_PREFIX")
print("EXPECT_PREFIX =", EXPECT_PREFIX)
sys.path.insert(0, os.path.join(EXPECT_PREFIX, "azure-pack"))


import azure
import azure.identity

print("azure.identity.__spec__ =", azure.identity.__spec__)
assert azure.identity.__spec__.origin.startswith(EXPECT_PREFIX)
assert type(azure.identity.__spec__.loader).__name__ == "DllPackLoader_azure"

import cryptography
print("cryptography.__spec__ =", cryptography.__spec__)
assert cryptography.__spec__.origin.startswith(EXPECT_PREFIX)
assert type(cryptography.__spec__.loader).__name__ == "DllPackLoader_cryptography"

import cryptography.hazmat.bindings._rust as cryptography_rust
print("cryptography_rust.__spec__ =", cryptography_rust.__spec__)
assert cryptography_rust.__spec__.origin.startswith(EXPECT_PREFIX)
assert type(cryptography_rust.__spec__.loader).__name__ == "ExtensionFileLoader"
