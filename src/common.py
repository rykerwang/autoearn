def dict2str(d):
    s = ""
    for k, v in d.items():
        s += f"{k}: {v}\n"
    return s