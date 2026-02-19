"""Logo generation with chromakey transparency, trimming, and compression."""

from __future__ import annotations

import base64
import io
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


def detect_project_type(repo_path: Path) -> str:
    """Detect project type from repository structure.

    Args:
        repo_path: Path to the repository

    Returns:
        Project type string (cli, library, web, api, framework, converter,
        database, security, or default)
    """
    # Check for Python CLI indicators
    if (repo_path / "pyproject.toml").exists():
        content = (repo_path / "pyproject.toml").read_text()
        if "[project.scripts]" in content:
            return "cli"
        if "[project.entry-points." in content:
            return "cli"

    # Check for package.json (Node.js)
    if (repo_path / "package.json").exists():
        content = (repo_path / "package.json").read_text()
        pkg = json.loads(content)
        if pkg.get("bin"):
            return "cli"
        if pkg.get("main") or pkg.get("module"):
            return "library"

    # Check for web frameworks
    if any(
        (repo_path / f).exists()
        for f in ["index.html", "vite.config.js", "next.config.js"]
    ):
        return "web"

    # Check for API indicators
    if any(
        (repo_path / f).exists() for f in ["openapi.yaml", "swagger.yaml", "api.yml"]
    ):
        return "api"

    # Check for database
    if any((repo_path / f).exists() for f in ["schema.sql", "migrations", "alembic"]):
        return "database"

    # Check for security-related
    if re.search(r"secur|auth|crypt|hash", repo_path.name, re.I):
        return "security"

    # Check for converter/transformer
    if re.search(r"convert|transform|migrat", repo_path.name, re.I):
        return "converter"

    # Check for framework
    if (repo_path / "src").is_dir() and len(list((repo_path / "src").iterdir())) > 3:
        return "framework"

    return "default"


def get_visual_metaphor(project_type: str) -> str:
    """Get visual metaphor for project type.

    Args:
        project_type: Type of project

    Returns:
        Visual metaphor description
    """
    metaphors = {
        "cli": "origami transformation, geometric terminal",
        "library": "interconnected building blocks",
        "web": "modern interface window",
        "api": "messenger bird carrying data packet",
        "framework": "architectural scaffold",
        "converter": "metamorphosis symbol",
        "database": "stacked cylinders, data nodes",
        "security": "shield, lock, key",
        "default": "abstract geometric shape",
    }
    return metaphors.get(project_type, metaphors["default"])


def build_prompt(project_name: str, project_type: str, config: dict[str, Any]) -> str:
    """Build image generation prompt from template.

    Args:
        project_name: Name of the project
        project_type: Type of project
        config: Logo configuration

    Returns:
        Complete prompt string
    """
    # Use custom template if provided
    if config.get("promptTemplate"):
        template = config["promptTemplate"]
    else:
        template = (
            "A {STYLE} logo for {PROJECT_NAME}: {VISUAL_METAPHOR}.\n"
            "Clean vector style. Icon colors from: {ICON_COLORS}.\n"
            "Pure {KEY_COLOR} background only. Do not use similar tones in the design.\n"
            "{TEXT_INSTRUCTIONS} Single centered icon, geometric shapes. "
            "The icon must fill the entire canvas edge-to-edge with minimal padding. "
            "No empty space around the design. Scalable to small sizes."
        )

    # Get visual metaphor
    visual_metaphor = config.get("visualMetaphor")
    if visual_metaphor is None:
        visual_metaphor = get_visual_metaphor(project_type)
    elif visual_metaphor == "none":
        visual_metaphor = ""

    # Build text instructions
    if config.get("includeRepoName", False):
        text_instructions = f'Include "{project_name}" as stylized text.'
    else:
        text_instructions = "No text, no letters, no words."

    # Format colors
    icon_colors = ", ".join(config.get("iconColors", ["#58a6ff", "#d29922", "#a371f7"]))

    # Substitute variables
    prompt = template.format(
        PROJECT_NAME=project_name,
        PROJECT_TYPE=project_type,
        VISUAL_METAPHOR=visual_metaphor,
        STYLE=config.get("style", "minimalist"),
        ICON_COLORS=icon_colors,
        KEY_COLOR=config.get("keyColor", "#00FF00"),
        TEXT_INSTRUCTIONS=text_instructions,
    )

    # Append additional instructions
    additional = config.get("additionalInstructions", "")
    if additional:
        prompt += f"\n{additional}"

    return prompt


def apply_chromakey(image_bytes: bytes, key_color: str, tolerance: int) -> bytes:
    """Apply chromakey transparency to image.

    Args:
        image_bytes: PNG image data
        key_color: Hex color to make transparent (e.g., '#00FF00')
        tolerance: Edge tolerance (0-255)

    Returns:
        PNG image data with transparency
    """
    from PIL import Image
    import io

    # Load image
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")

    # Parse key color
    key_color = key_color.lstrip("#")
    key_r = int(key_color[0:2], 16)
    key_g = int(key_color[2:4], 16)
    key_b = int(key_color[4:6], 16)

    # Get pixel data
    data = img.getdata()
    new_data = []

    for item in data:
        r, g, b, a = item
        # Calculate distance from key color
        distance = ((r - key_r) ** 2 + (g - key_g) ** 2 + (b - key_b) ** 2) ** 0.5

        if distance < tolerance:
            # Make transparent
            new_data.append((r, g, b, 0))
        else:
            new_data.append(item)

    img.putdata(new_data)

    # Save to bytes
    output = io.BytesIO()
    img.save(output, format="PNG")
    return output.getvalue()


def trim_transparent(image_bytes: bytes, margin: int = 5) -> bytes:
    """Trim transparent padding from image.

    Args:
        image_bytes: PNG image data with transparency
        margin: Margin percentage (0-25)

    Returns:
        Trimmed PNG image data
    """
    from PIL import Image
    import io

    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    original_width, original_height = img.size

    # Get alpha channel
    alpha = img.split()[3]
    bbox = alpha.getbbox()

    if bbox is None:
        # Fully transparent
        return image_bytes

    # Calculate margin in pixels
    larger_dim = max(original_width, original_height)
    margin_px = int(larger_dim * margin / 100)

    # Expand bbox
    expanded_bbox = (
        max(0, bbox[0] - margin_px),
        max(0, bbox[1] - margin_px),
        min(original_width, bbox[2] + margin_px),
        min(original_height, bbox[3] + margin_px),
    )

    # Crop and resize back
    cropped = img.crop(expanded_bbox)
    resized = cropped.resize((original_width, original_height), Image.LANCZOS)

    # Save to bytes
    output = io.BytesIO()
    resized.save(output, format="PNG")
    return output.getvalue()


def compress_png(image_bytes: bytes, quality: int = 80) -> bytes:
    """Compress PNG image.

    Args:
        image_bytes: PNG image data
        quality: Compression quality (0-100, higher is better quality)

    Returns:
        Compressed PNG image data
    """
    from PIL import Image
    import io

    img = Image.open(io.BytesIO(image_bytes))

    # Save with optimization
    output = io.BytesIO()

    # PIL doesn't have quality for PNG, but we can optimize
    img.save(output, format="PNG", optimize=True)

    return output.getvalue()


def generate_logo(repo_path: Path, config: dict[str, Any], api_key: str) -> Path:
    """Generate a logo for the repository.

    Args:
        repo_path: Path to the repository
        config: Logo configuration
        api_key: OpenRouter API key

    Returns:
        Path to generated logo file
    """
    import requests

    project_name = repo_path.name
    project_type = detect_project_type(repo_path)
    prompt = build_prompt(project_name, project_type, config)

    # Resolve output path
    output_path = config.get("outputPath", "logo.png")
    if "{PROJECT_NAME}" in output_path:
        output_path = output_path.replace("{PROJECT_NAME}", project_name)
    output_path = repo_path / output_path

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate image via OpenRouter
    model = config.get("model", "google/gemini-3-pro-image-preview")
    size = config.get("size", "1K")

    # Map size to dimensions
    size_map = {
        "1K": "1024x1024",
        "2K": "2048x2048",
        "512": "512x512",
        "256": "256x256",
    }
    dimensions = size_map.get(size, "1024x1024")

    response = requests.post(
        "https://openrouter.ai/api/v1/images/generations",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "prompt": prompt,
            "size": dimensions,
            "n": 1,
        },
        timeout=120,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Image generation failed: {response.status_code} - {response.text}"
        )

    result = response.json()

    # Get image URL or base64 data
    if "data" in result and len(result["data"]) > 0:
        image_data = result["data"][0]
        if "b64_json" in image_data:
            image_bytes = base64.b64decode(image_data["b64_json"])
        elif "url" in image_data:
            # Download from URL
            img_response = requests.get(image_data["url"], timeout=60)
            img_response.raise_for_status()
            image_bytes = img_response.content
        else:
            raise RuntimeError("No image data in response")
    else:
        raise RuntimeError("No image data in response")

    # Apply chromakey transparency
    key_color = config.get("keyColor", "#00FF00")
    tolerance = config.get("tolerance", 70)
    image_bytes = apply_chromakey(image_bytes, key_color, tolerance)

    # Trim transparent padding if enabled
    if config.get("trim", True):
        margin = config.get("trimMargin", 5)
        image_bytes = trim_transparent(image_bytes, margin)

    # Compress if enabled
    if config.get("compress", True):
        quality = config.get("compressQuality", 80)
        image_bytes = compress_png(image_bytes, quality)

    # Write output
    output_path.write_bytes(image_bytes)

    return output_path
