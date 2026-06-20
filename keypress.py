import sys
def keypress(character: str):
    if sys.platform.startswith("win"):  # weeee microslop
        import msvcrt

        return msvcrt.getch().decode("utf-8", errors="ignore")
    else:
        import tty
        import termios

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch == character
