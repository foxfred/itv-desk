import datetime

_EPOCH = datetime.datetime(1970, 1, 1)


def has_catchup(channel):
    return bool((channel.get("catchup") or "").strip()
                or (channel.get("catchup_source") or "").strip())


def _apply_template(tpl, values):
    out = str(tpl)
    for key, val in values.items():
        out = out.replace(key, val)
    return out


def build_catchup_url(channel, start_dt, end_dt):
    """Build a catch-up url for one program window; None when unsupported."""
    url = (channel.get("url") or "").strip()
    if not url:
        return None
    mode = (channel.get("catchup") or "").strip().lower()
    source = (channel.get("catchup_source") or "").strip().replace("&amp;", "&")

    duration = int((end_dt - start_dt).total_seconds())
    if duration <= 0:
        duration = 3600
    utc = int((start_dt - _EPOCH).total_seconds())
    utcend = int((end_dt - _EPOCH).total_seconds())
    stamp = str(int(start_dt.timestamp()))

    values = {
        "${start}": start_dt.strftime("%Y%m%d%H%M%S"),
        "${end}": end_dt.strftime("%Y%m%d%H%M%S"),
        "${utcend}": str(utcend),
        "${utc}": str(utc),
        "${lutc}": str(utc),
        "${duration}": str(duration),
        "${timestamp}": stamp,
        "{start}": start_dt.strftime("%Y%m%d%H%M%S"),
        "{end}": end_dt.strftime("%Y%m%d%H%M%S"),
        "{utcend}": str(utcend),
        "{utc}": str(utc),
        "{lutc}": str(utc),
        "{duration}": str(duration),
        "{timestamp}": stamp,
    }

    sep = "&" if "?" in url else "?"

    if mode == "append":
        return "%s%sutc=%d&lutc=%d" % (url, sep, utc, utc)
    if mode in ("flussonic", "fs"):
        return "%s%sstart=%d&end=%d" % (url, sep, utc, utcend)
    if mode in ("xc", "xtream"):
        fmt = "%Y-%m-%d:%H-%M-%S"
        return "%s%sstart=%s&end=%s" % (url, sep, start_dt.strftime(fmt), end_dt.strftime(fmt))
    if source:
        out = _apply_template(source, values)
        if out.startswith("http://") or out.startswith("https://"):
            return out
        base = url.split("?", 1)[0]
        if out.startswith("?"):
            return base + out
        return base + ("&" if "?" in url else "?") + out.lstrip("?&")
    if mode:
        return "%s%sutc=%d&lutc=%d" % (url, sep, utc, utc)
    return None
