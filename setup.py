from pip._internal.cli.main import main
from sys import platform


common_packages = [
    "beautifulsoup4>=4.11.1",
    "colorama>=0.4.6",
    "requests>=2.28.1",
    "pytelegrambotapi>=4.8.0",
    "pillow>=9.3.0",
    "vk_api>=11.9.9",
    "aiohttp>=3.8.3"
]

linux = [
    "lxml"
]

windows = [
    "./lxml-4.9.0-cp311-cp311-win_amd64.whl"
]


def install_packages(packages_list: list[str]):
    for pkg in packages_list:
        main(["install", pkg])


if __name__ == '__main__':
    install_packages(common_packages)
    print(platform)
    if "win" in platform:
        install_packages(windows)
    elif "linux" in platform:
        install_packages(linux)
