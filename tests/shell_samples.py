"""The M1 example file (M1 Brief > Scope of the File) and helpers to write it."""

from __future__ import annotations

from pathlib import Path

HEADER = "---\nTDL: 0.1\nShell: 0.1\nName: Main_Shell\n---\n"

SVG = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 4 4'><rect width='4' height='4'/></svg>"

BODY = """
Shell {
    Monitor {
        Name: Main
        Index: 0
        Children {
            Bar {
                Name: Top_Bar
                Edge: TOP
                Width: EXPAND
                Height: 32
                Style { Fill: "#1f1f1f" }
                Children {
                    FlexBox {
                        Width: EXPAND
                        Flex: HORIZONTAL
                        Spacing: 8
                        Padding: 4
                        Children {
                            Text { Text: "14:05", Font_Size: 14, Foreground: "#ffffff" }
                            Spacer { }
                            SVG { Source: "dot.svg", Width: 16, Height: 16, Color: "#89b4fa" }
                            Rectangle { Width: 12, Height: 12, Fill: "#89b4fa", Corner_Radius: 6 }
                        }
                    }
                }
            }
        }
    }
}
"""


def write_example(config: Path, body: str = BODY, name: str = "Main_Shell.tdl") -> Path:
    shells = config / "Shells"
    shells.mkdir(parents=True, exist_ok=True)
    (shells / "dot.svg").write_text(SVG)
    path = shells / name
    path.write_text(HEADER + body)
    return path
