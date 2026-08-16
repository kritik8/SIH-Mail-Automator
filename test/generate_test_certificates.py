import os
from pathlib import Path
from PIL import Image, ImageDraw

def generate_certificates(output_dir: Path, count: int = 12) -> None:
    """Generates `count` simple placeholder certificate PNGs with border and text."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Minimalist certificate design parameters
    width, height = 800, 600
    bg_color = (255, 255, 255)       # White
    border_color = (30, 58, 138)     # Navy Blue (#1E3A8A)
    text_color = (51, 51, 51)        # Neutral Dark (#333333)

    for i in range(1, count + 1):
        filename = f"{i:03d}.png"
        filepath = output_dir / filename
        
        # Create image canvas
        image = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(image)
        
        # Draw a double navy border
        draw.rectangle([(10, 10), (width - 10, height - 10)], outline=border_color, width=4)
        draw.rectangle([(18, 18), (width - 18, height - 18)], outline=border_color, width=1)
        
        # Draw placeholder text
        draw.text((width // 2, 80), "SMART INDIA HACKATHON 2026", fill=border_color, anchor="mm")
        draw.text((width // 2, 130), "INTERNAL HACKATHON PARTICIPATION", fill=text_color, anchor="mm")
        
        draw.text((width // 2, 250), "CERTIFICATE OF PARTICIPATION", fill=border_color, anchor="mm")
        
        draw.text((width // 2, 350), f"This is to certify that Team Member", fill=text_color, anchor="mm")
        draw.text((width // 2, 390), f"successfully contributed to Team Registration #{((i - 1) // 6) + 1}", fill=text_color, anchor="mm")
        
        draw.text((width // 2, 480), f"Certificate Serial: {i:03d}", fill=(119, 119, 119), anchor="mm")
        draw.text((width // 2, 520), "Indian Institute of Information Technology, Bhopal", fill=border_color, anchor="mm")
        
        # Save image
        image.save(filepath, "PNG")
        print(f"Generated placeholder certificate: {filepath.name}")

if __name__ == "__main__":
    certs_directory = Path(__file__).parent / "certificates"
    print(f"Generating test certificates under: {certs_directory.absolute()}")
    generate_certificates(certs_directory, count=12)
