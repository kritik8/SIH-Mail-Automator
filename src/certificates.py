import logging
from pathlib import Path
from typing import List

logger = logging.getLogger("certificates")

class CertificateError(Exception):
    pass

def get_certificate_files(team_number: str, certs_dir: Path) -> List[Path]:
    """
    Assigns and verifies 6 certificate PNG paths for the given team_number.
    
    Rule:
      For team index n (parsed from team_number):
      Files mapped are ((n-1)*6 + 1) to (n*6), zero-padded to 3 digits (e.g. 001.png).
    """
    try:
        # Convert team number to integer (e.g., "01" -> 1, "SIH-64" -> 64)
        num_str = team_number.strip()
        if num_str.upper().startswith("SIH-"):
            num_str = num_str[4:]
        n = int(num_str)
    except ValueError:
        raise CertificateError(f"Invalid team_number format: '{team_number}'. Must be a sequential integer string.")

    if n <= 0:
        raise CertificateError(f"Team number must be a positive non-zero integer: got {n}.")

    # Compute range of certificate IDs
    start_id = (n - 1) * 6 + 1
    end_id = n * 6
    
    cert_paths = []
    missing_files = []
    
    for i in range(start_id, end_id + 1):
        filename = f"{i:03d}.png"
        filepath = certs_dir / filename
        cert_paths.append(filepath)
        if not filepath.exists():
            missing_files.append(filename)

    if missing_files:
        raise FileNotFoundError(
            f"Missing certificates in pool for Team {team_number} (range {start_id:03d}-{end_id:03d}): "
            f"Missing files: {', '.join(missing_files)}"
        )
        
    return cert_paths
