from scripts.gpu_metrics_exporter import parse_nvidia_smi_csv, render_prometheus


def test_parse_nvidia_smi_csv_handles_multiple_gpus() -> None:
    rows = parse_nvidia_smi_csv(
        [
            "NVIDIA GeForce RTX 3090, 23853, 24576, 100, 46",
            "NVIDIA GeForce RTX 2060, 3444, 6144, 22, 43",
        ]
    )

    assert rows == [
        {
            "gpu": "0",
            "name": "NVIDIA GeForce RTX 3090",
            "memory_used_mib": 23853.0,
            "memory_total_mib": 24576.0,
            "gpu_util_percent": 100.0,
            "temperature_c": 46.0,
        },
        {
            "gpu": "1",
            "name": "NVIDIA GeForce RTX 2060",
            "memory_used_mib": 3444.0,
            "memory_total_mib": 6144.0,
            "gpu_util_percent": 22.0,
            "temperature_c": 43.0,
        },
    ]


def test_render_prometheus_exposes_dcgm_compatible_metric_names() -> None:
    text = render_prometheus(
        [
            {
                "gpu": "0",
                "name": "NVIDIA GeForce RTX 3090",
                "memory_used_mib": 23853.0,
                "memory_total_mib": 24576.0,
                "gpu_util_percent": 100.0,
                "temperature_c": 46.0,
            }
        ]
    )

    assert 'DCGM_FI_DEV_GPU_UTIL{gpu="0",modelName="NVIDIA GeForce RTX 3090"} 100.0' in text
    assert 'DCGM_FI_DEV_FB_USED{gpu="0",modelName="NVIDIA GeForce RTX 3090"} 23853.0' in text
    assert 'DCGM_FI_DEV_FB_FREE{gpu="0",modelName="NVIDIA GeForce RTX 3090"} 723.0' in text
    assert 'DCGM_FI_DEV_GPU_TEMP{gpu="0",modelName="NVIDIA GeForce RTX 3090"} 46.0' in text
