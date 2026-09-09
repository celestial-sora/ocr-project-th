# -*- coding: utf-8 -*-
import os

LINE_CHANNEL_ACCESS_TOKEN = "bXB7RjgrSXw7eSUfxY6tE+Evv7ZZaIM6R9EeTJUv8ROnYWR4jWcrFGyEBcDUJ6z9dmgnbMZ86QddoufkGs94vbyJWStWvHZxcCOZPuttCLImv/6aR0j9Ny4sX1n4ZSdgR2pZRr2PEFuYd/fvS0XcvwdB04t89/1O/w1cDnyilFU="
LINE_PUSH_TO = "U986fb0aeca4be80b25d681ddbc2d68a6"


def get_line_channel_access_token() -> str:
    return os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", LINE_CHANNEL_ACCESS_TOKEN).strip()


def get_line_push_to() -> str:
    return os.environ.get("LINE_PUSH_TO", LINE_PUSH_TO).strip()
