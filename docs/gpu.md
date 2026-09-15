# GPU host preparation

Worker and hybrid installation runs `prepare-gpu.sh`; pure controllers do not. The supported CPU architectures are amd64 and arm64. Host preparation installs available Debian 13 vendor stacks and NVIDIA's container toolkit, then leaves Kubernetes GPU scheduling to the chosen device plugin/operator. It never reports a GPU as schedulable merely because packages installed.

| Vendor/family | Host preparation | Later cluster integration |
| --- | --- | --- |
| NVIDIA | Firmware where packaged, NVIDIA container toolkit on workers; `nvidia-driver`, OpenCL and `nvidia-smi` on detected display/3D NVIDIA hardware | NVIDIA device plugin/GPU Operator; use host-driver mode (`driver.enabled=false`) when retaining these drivers |
| AMD | In-kernel amdgpu, AMD firmware, Mesa; ROCm OpenCL/HSA/HIP userspace where Debian provides it for the architecture | AMD device plugin/operator; verify `/dev/kfd` and `/dev/dri` and supported GPU generation |
| Intel | In-kernel i915/xe, Intel firmware, Mesa; OpenCL, Level Zero and media runtime packages where available | Intel device plugins or the matching DRA driver; verify render nodes and model-specific support |
| Other Mesa-supported GPUs | Mesa Vulkan, DRI and OpenCL plus Debian generic firmware | A compatible device plugin or explicit device allocation appropriate to that driver/hardware |

“All vendors in the repository” is interpreted as all available host stacks in Debian 13's signed `main`, `contrib`, `non-free`, and `non-free-firmware` archives, plus NVIDIA's official container-runtime repository. Optional architecture-dependent packages are probed and their absence is recorded in `/var/log/elektro-gpu-packages.log`; failures installing an available package stop provisioning. Mesa covers additional hardware families as supported by its Debian build. There is no universal package that makes every past or future GPU support compute.

The default NVIDIA package follows Debian's supported driver selection. Run `nvidia-detect` and inspect its result. Very new GPUs, legacy models, vGPU, vendor-certified ROCm releases and specialized accelerators may require a different supported OS/kernel/vendor repository. Do not assume Debian's ROCm userspace version is interchangeable with every upstream container image. The script does not silently claim support for unavailable hardware/software.

After package installation, reboot before joining production GPU workloads:

```bash
sudo reboot
# After reconnecting:
sudo bash scripts/verify-gpu.sh
```

For NVIDIA, k3s discovers `nvidia-container-runtime` at service startup and generates runtime handlers in its own containerd configuration. Install the toolkit before starting k3s, or restart `k3s` / `k3s-agent` after adding it. Do not modify `/etc/containerd/config.toml` and expect it to configure k3s. Check that a `nvidia` RuntimeClass exists before scheduling pods that request it. [k3s runtime configuration](https://docs.k3s.io/advanced).

NVIDIA CDI generation runs when an active driver is available. After a reboot or driver change, regenerate `/etc/cdi/nvidia.yaml` with `sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml`, or use the toolkit's refresh service if supplied by the installed version. Use either the documented runtime path or the operator's CDI setup consistently.

Secure Boot can prevent DKMS modules from loading. The script detects enabled Secure Boot but cannot complete firmware enrollment non-interactively. Follow Debian's MOK enrollment procedure for the generated DKMS signing certificate, reboot, and verify `nvidia-smi`; do not disable signature verification merely to suppress an installation symptom.

On AMD/Intel verify kernel device nodes, firmware logs and actual OpenCL/Level Zero compatibility. Grant device access through the relevant device plugin; do not make every application privileged or make device nodes world-writable. GPU libraries inside workload images should match the selected host driver/runtime support matrix.

No GPU operator is enabled by default because device generation, desired sharing/MIG/SR-IOV policy and vendor support constraints are unknown. The supplied host prerequisites let you select one without rebuilding the base. Never combine an operator-managed driver installation with conflicting host driver management.

Primary references: [Debian NVIDIA OpenCL](https://packages.debian.org/trixie/nvidia-opencl-icd), [Debian ROCm OpenCL](https://packages.debian.org/trixie/rocm-opencl-icd), [NVIDIA container toolkit installation](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html), and [k3s advanced configuration](https://docs.k3s.io/advanced).
