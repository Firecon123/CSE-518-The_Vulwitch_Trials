import torch
print(torch.version.cuda)       # Should show 12.1
print(torch.cuda.is_available()) # Should be True
print(torch.cuda.device_count()) # Should be >= 1
print(torch.cuda.get_device_name(0)) # Your GPU name
