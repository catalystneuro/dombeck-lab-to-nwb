import os


def main():
    os.system("pip freeze --exclude dombeck-lab-to-nwb > frozen_dependencies.txt")


if __name__ == "__main__":
    main()
