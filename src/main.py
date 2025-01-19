import asyncio
import threading
from autoearn import AutoEarn
import argparse
from webapp import create_app  # 新增导入

def main():
    parser = argparse.ArgumentParser(description="A script that reads a YAML configuration file.")
    parser.add_argument(
        '-c', '--config', 
        help="Path to the YAML configuration file."
    )
    parser.add_argument(
        '-w', '--web', 
        action='store_true', 
        help="Start the Flask webapp."
    )
    parser.add_argument(
        '-a', '--autorun', 
        action='store_true', 
        help="Start the AutoEarn process."
    )

    args = parser.parse_args()

    if args.web:
        start_webapp()
    elif args.autorun:
        if not args.config:
            parser.error("-a/--autorun requires -c/--config.")
        start_autoearn(args.config)
    else:
        parser.print_help()

def start_autoearn(config_path):
    autoearn = AutoEarn.from_config(config_path)
    autoearn.start()

def start_webapp():
    webapp = create_app()
    webapp.run(host='0.0.0.0', port=5001)

if __name__ == "__main__":
    main()
