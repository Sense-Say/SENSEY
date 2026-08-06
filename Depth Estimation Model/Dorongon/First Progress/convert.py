import torch
import os
from depth_anything_v2.dpt import DepthAnythingV2

# 1. SETUP THE MODEL ARCHITECTURE
# This matches the 'vits' (Small) configuration
model_configs = {
    'vits': {'encoder': 'vits', 'features': 64, 'out_channels': [48, 96, 192, 384]}
}

print("Initializing model structure...")
model = DepthAnythingV2(**model_configs['vits'])

# 2. LOAD YOUR WEIGHTS
pth_file = 'depth_anything_v2_vits.pth'

if not os.path.exists(pth_file):
    print(f"Error: {pth_file} not found! Please put it in the same folder as this script.")
else:
    print(f"Loading weights from {pth_file}...")
    # Map to CPU because RPi doesn't have CUDA
    model.load_state_dict(torch.load(pth_file, map_location='cpu'))
    model.eval()

    # 3. CREATE DUMMY INPUT (Define the Resolution here)
    # IMPORTANT: We set the resolution to 252x252. 
    # This ensures the ONNX model is hard-coded for speed on the Pi.
    h, w = 252, 252
    dummy_input = torch.randn(1, 3, h, w)

    # 4. EXPORT TO ONNX
    output_file = "depth_anything_v2_vits.onnx"
    print(f"Exporting to {output_file}... this might take a minute...")

    torch.onnx.export(
        model,
        dummy_input,
        output_file,
        opset_version=11,
        input_names=['input'],
        output_names=['depth'],
        # We allow dynamic batch size, but keep H/W static for optimization
        dynamic_axes={'input': {0: 'batch_size'}, 'depth': {0: 'batch_size'}} 
    )

    print("-----------------------------------")
    print("SUCCESS!")
    print(f"New file created: {output_file}")
    print("You can now use this .onnx file with the live video script.")