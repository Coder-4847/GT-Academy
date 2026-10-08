"""Process configuration must run before importing torch/NumPy in workers."""
import os


def configure_environment() -> None:
    for name in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        os.environ[name]='1'
    os.environ['CUDA_VISIBLE_DEVICES']=''


def set_priority(priority: str = 'below-normal') -> None:
    if priority=='normal':
        return
    if os.name=='nt':
        import ctypes
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.GetCurrentProcess.restype=wintypes.HANDLE
        kernel.SetPriorityClass.argtypes=(wintypes.HANDLE,wintypes.DWORD)
        level=0x00004000 if priority=='below-normal' else 0x00000040
        if not kernel.SetPriorityClass(kernel.GetCurrentProcess(),level):
            raise OSError(ctypes.get_last_error(),'Could not lower training process priority')
    else:
        os.nice(5 if priority=='below-normal' else 10)


def configure_torch() -> None:
    import torch
    torch.set_num_threads(1)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
