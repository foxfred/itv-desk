"""DLNA 投屏服务 - SSDP 发现 + UPnP AVTransport 控制。

说明：
- 发现基于 SSDP 多播（239.255.255.250:1900），仅找 MediaRenderer 设备；
- 播放基于 UPnP AVTransport 的 SetAVTransportURI + Play（SOAP）；
- 全程 try/except 包裹，任何网络异常都不会击穿主流程；
- 沙箱/无设备环境下 discover() 返回空列表且不抛错，真实局域网中可用。
"""
import os
import time
import socket
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

SSDP_ADDR = "239.255.255.250"
SSDP_PORT = 1900
SSDP_TARGET = (SSDP_ADDR, SSDP_PORT)
DISCOVER_MSG = (
    'M-SEARCH * HTTP/1.1\r\n'
    f'HOST: {SSDP_ADDR}:{SSDP_PORT}\r\n'
    'MAN: "ssdp:discover"\r\n'
    'MX: 3\r\n'
    'ST: urn:schemas-upnp-org:device:MediaRenderer:1\r\n'
    '\r\n'
)

# UPnP 设备/服务命名空间
_UPNP_NS = {'u': 'urn:schemas-upnp-org:device-1-0'}


class DlnaService:
    def __init__(self, log_callback=None):
        self.log_callback = log_callback or (lambda m: None)
        self.devices = []

    # -------------------- 发现 --------------------
    def discover(self, timeout=3):
        """SSDP 发现局域网内 MediaRenderer 设备，返回设备列表（含 control_url）"""
        found = {}
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(timeout)
            sock.sendto(DISCOVER_MSG.encode('utf-8'), SSDP_TARGET)
            deadline = time.time() + timeout
            while True:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                sock.settimeout(max(0.1, remaining))
                try:
                    data, _addr = sock.recvfrom(4096)
                except socket.timeout:
                    break
                text = data.decode('utf-8', errors='ignore')
                location = self._header(text, 'LOCATION')
                if location and location not in found:
                    dev = self._describe(location)
                    if dev:
                        found[location] = dev
        except Exception as e:
            self.log_callback(f"DLNA 发现出错: {e}")
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass
        self.devices = list(found.values())
        self.log_callback(f"DLNA 发现到 {len(self.devices)} 个可投屏设备")
        return self.devices

    @staticmethod
    def _header(text, name):
        for line in text.splitlines():
            if line.lower().startswith(name.lower() + ':'):
                return line.split(':', 1)[1].strip()
        return None

    def _describe(self, location):
        try:
            req = urllib.request.Request(location, headers={'User-Agent': 'IPTV-Core/1.0'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                xml_text = resp.read().decode('utf-8', errors='ignore')
            return self._parse_device(xml_text, location)
        except Exception as e:
            self.log_callback(f"DLNA 描述获取失败 {location}: {e}")
            return None

    @staticmethod
    def _local(tag):
        """取元素 local name（忽略命名空间前缀/默认命名空间）"""
        return tag.split('}')[-1]

    @staticmethod
    def _find_local(el, local_name):
        """在 el 后代中按 local name 查找文本（命名空间无关，UPnP 描述前缀多变）"""
        for child in el.iter():
            if child is el:
                continue
            if DlnaService._local(child.tag) == local_name and child.text:
                return child.text.strip()
        return None

    def _parse_device(self, xml_text, location):
        try:
            root = ET.fromstring(xml_text)
            device = None
            for d in root.iter():
                if self._local(d.tag) == 'device':
                    dt = self._find_local(d, 'deviceType') or ''
                    if dt.endswith('MediaRenderer'):
                        device = d
                        break
            if device is None:
                for d in root.iter():
                    if self._local(d.tag) == 'device':
                        device = d
                        break
            if device is None:
                return None
            name = self._find_local(device, 'friendlyName') or 'DLNA 设备'
            ctrl = None
            for svc in device.iter():
                if self._local(svc.tag) == 'service':
                    st = self._find_local(svc, 'serviceType') or ''
                    if 'AVTransport' in st:
                        ctrl = self._find_local(svc, 'controlURL')
                        break
            if not ctrl:
                return None
            return {"name": name, "location": location, "control_url": self._abs_url(location, ctrl)}
        except Exception:
            return None

    @staticmethod
    def _abs_url(base, path):
        if path.startswith('http'):
            return path
        p = urlparse(base)
        return f"{p.scheme}://{p.netloc}{path}"

    # -------------------- 控制（SOAP） --------------------
    def _soap(self, control_url, action, body_inner):
        import http.client
        u = urlparse(control_url)
        conn = http.client.HTTPConnection(u.netloc, timeout=5)
        soap = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
            's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
            f'<s:Body>{body_inner}</s:Body></s:Envelope>'
        )
        headers = {
            'Content-Type': 'text/xml; charset="utf-8"',
            'SOAPACTION': f'"urn:schemas-upnp-org:service:AVTransport:1#{action}"',
        }
        conn.request('POST', u.path or '/', soap.encode('utf-8'), headers)
        resp = conn.getresponse()
        data = resp.read().decode('utf-8', errors='ignore')
        conn.close()
        return resp.status, data

    def play(self, device, url):
        """向设备推送并播放指定直播源（SetAVTransportURI + Play）"""
        if isinstance(device, str):
            device = next((d for d in self.devices if d.get("name") == device), None)
        if not isinstance(device, dict):
            return {"error": "无效设备"}
        control_url = device.get("control_url")
        name = device.get("name", "设备")
        if not control_url:
            return {"error": "设备无 AVTransport 控制地址"}
        didl = self._didl(url)
        body = (
            '<u:SetAVTransportURI xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            '<InstanceID>0</InstanceID>'
            f'<CurrentURI>{self._esc(url)}</CurrentURI>'
            f'<CurrentURIMetaData>{self._esc(didl)}</CurrentURIMetaData>'
            '</u:SetAVTransportURI>'
        )
        try:
            st, _ = self._soap(control_url, "SetAVTransportURI", body)
            if st == 200:
                play_body = (
                    '<u:Play xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
                    '<InstanceID>0</InstanceID><Speed>1</Speed></u:Play>'
                )
                st2, _ = self._soap(control_url, "Play", play_body)
                ok = st2 == 200
                self.log_callback(f"DLNA 投屏到 {name}：{'成功' if ok else '播放指令失败'}")
                return {"ok": ok, "status": st2}
            return {"error": f"SetAVTransportURI 失败，状态码 {st}"}
        except Exception as e:
            return {"error": str(e)}

    def stop(self, device):
        """停止设备当前播放"""
        if isinstance(device, str):
            device = next((d for d in self.devices if d.get("name") == device), None)
        if not isinstance(device, dict):
            return {"error": "无效设备"}
        control_url = device.get("control_url")
        if not control_url:
            return {"error": "设备无 AVTransport 控制地址"}
        body = (
            '<u:Stop xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            '<InstanceID>0</InstanceID></u:Stop>'
        )
        try:
            st, _ = self._soap(control_url, "Stop", body)
            return {"ok": st == 200, "status": st}
        except Exception as e:
            return {"error": str(e)}

    # -------------------- 工具 --------------------
    @staticmethod
    def _esc(s):
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    def _didl(self, url):
        title = url.split("/")[-1] or "IPTV Stream"
        return (
            '<DIDL-Lite xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/" '
            'xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/">'
            '<item id="0" parentID="-1" restricted="0">'
            f'<dc:title>{self._esc(title)}</dc:title>'
            '<upnp:class>object.item.videoItem</upnp:class>'
            f'<res protocolInfo="http-get:*:video/mpeg:*">{self._esc(url)}</res>'
            '</item></DIDL-Lite>'
        )
