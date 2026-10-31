"""Run with: python main.py"""
def main():
    try:
        from game import run
        run()
    except ImportError as exc:
        print(f'GUI module could not be imported: {exc}')
        print('Install Python with Tcl/Tk support. Check: python -m tkinter')
        raise SystemExit(1) from exc
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
