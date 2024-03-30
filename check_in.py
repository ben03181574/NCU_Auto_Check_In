import os
import json
from auto_check_in import (
    main
)

if __name__ == "__main__":
    args = dict()
    with open(os.path.dirname(__file__)+'/config.json', 'r', encoding='utf-8') as f:
        args.update(json.load(f))

    main(args, "check-in")