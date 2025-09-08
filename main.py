from app import TrayApplication


def main() -> None:
    """
    Application entry point:
    Create and run the tray application.
    """
    app = TrayApplication()
    app.run()


if __name__ == "__main__":
    main()
