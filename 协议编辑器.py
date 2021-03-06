import datetime
import tkinter
from tkinter import *
from tkinter.constants import *
from tkinter.ttk import Treeview, Style
from scapy.all import *
from scapy.layers.inet import *
from scapy.layers.l2 import *

tk = tkinter.Tk()
tk.title("协议编辑器")
# 使窗体最大化
tk.state("zoomed")
# 左右分隔窗体
main_panedwindow = PanedWindow(tk, sashrelief=RAISED, sashwidth=5)
# 协议编辑区窗体
protocol_editor_panedwindow = PanedWindow(orient=VERTICAL, sashrelief=RAISED, sashwidth=5)
# 协议导航树
protocols_tree = Treeview()
# 默认发送地址
default_dst = '10.5.24.211'
# 用来终止数据包发送线程的线程事件
stop_sending = threading.Event()

# 状态栏类
class StatusBar(Frame):
    def __init__(self, master):
            Frame.__init__(self, master)
            self.label = Label(self, bd=1, relief=SUNKEN, anchor=W)
            self.label.pack(fill=X)
    def set(self, fmt, *args):
            self.label.config(text=fmt % args)
            self.label.update_idletasks()
    def clear(self):
            self.label.config(text="")
            self.label.update_idletasks()

# 状态栏
status_bar = StatusBar(tk)
status_bar.pack(side=BOTTOM, fill=X)
status_bar.set("%s", '开始')

"""
创建协议导航树
:return: 协议导航树
"""
def create_protocols_tree():
    
    protocols_tree.heading('#0', text='选择网络协议', anchor='w')
    # 参数:parent, index, iid=None, **kw (父节点，插入的位置，id，显示出的文本)
    # 应用层
    applicatoin_layer_tree_entry = protocols_tree.insert("", 0, "应用层", text="应用层")  # ""表示父节点是根
    http_packet_tree_entry = protocols_tree.insert(applicatoin_layer_tree_entry, 1, "HTTP报文", text="HTTP报文")
    transfer_layer_tree_entry = protocols_tree.insert("", 1, "运输层", text="运输层")
    tcp_packet_tree_entry = protocols_tree.insert(transfer_layer_tree_entry, 0, "TCP报文", text="TCP报文")
    udp_packet_tree_entry = protocols_tree.insert(transfer_layer_tree_entry, 1, "UDP报文", text="UDP报文")
    # 网络层
    ip_layer_tree_entry = protocols_tree.insert("", 2, "网络层", text="网络层")
    ip_packet_tree_entry = protocols_tree.insert(ip_layer_tree_entry, 0, "IP报文", text="IP报文")
    icmp_packet_tree_entry = protocols_tree.insert(ip_layer_tree_entry, 1, "ICMP报文", text="ICMP报文")
    arp_packet_tree_entry = protocols_tree.insert(ip_layer_tree_entry, 2, "ARP报文", text="ARP报文")
    # 数据链路层
    ether_layer_tree_entry = protocols_tree.insert("", 3, "数据链路层", text="数据链路层")
    mac_frame_tree_entry = protocols_tree.insert(ether_layer_tree_entry, 1, "以太网MAC帧", text="以太网MAC帧")
    protocols_tree.bind('<<TreeviewSelect>>', on_click_protocols_tree)
    style = Style(tk)
    # get disabled entry colors
    disabled_bg = style.lookup("TEntry", "fieldbackground", ("disabled",))
    style.map("Treeview",
                        fieldbackground=[("disabled", disabled_bg)],
                            foreground=[("disabled", "gray")],
                            background=[("disabled", disabled_bg)])
    protocols_tree.pack()
    return protocols_tree

"""
使protocols_tree失效
:rtype: None
"""
def toggle_protocols_tree_state():
    
    if "disabled" in protocols_tree.state():
            protocols_tree.state(("!disabled",))
            # re-enable item opening on click
            protocols_tree.unbind('<Button-1>')
    else:
        protocols_tree.state(("disabled",))
        # disable item opening on click
        protocols_tree.bind('<Button-1>', lambda event: 'break')

"""
协议导航树单击事件响应函数
:param event: TreeView单击事件
:return: None
"""
def on_click_protocols_tree(event):
    # event.widget获取Treeview对象，调用selection获取选择对象名称
    selected_item = event.widget.selection()
    # 清空protocol_editor_panedwindow上现有的控件
    for widget in protocol_editor_panedwindow.winfo_children():
        widget.destroy()
    # 设置状态栏
    status_bar.set("%s", selected_item[0])
    if selected_item[0] == "以太网MAC帧":
        create_mac_sender()
    elif selected_item[0] == "ARP报文":
        create_arp_sender()
    elif selected_item[0] == "IP报文":
        create_ip_sender()
    elif selected_item[0] == "ICMP报文":
        create_icmp_sender()
    elif selected_item[0] == "TCP报文":
        create_tcp_sender()
    elif selected_item[0] == "UDP报文":
        create_udp_sender()
    elif selected_item[0] == "HTTP报文":
        create_http_sender()

"""
创建协议字段编辑区
:param root: 协议编辑区
:param field_names: 协议字段名列表
:return: 协议字段编辑框列表
"""
def create_protocol_editor(root, field_names):
    
    entries = []
    for field in field_names:
        row = Frame(root)
        label = Label(row, width=15, text=field, anchor='e')
        # 设置编辑框为等宽字体
        entry = Entry(row, font=('Courier', '12', 'bold'), state='normal')
        row.pack(side=TOP, fill=X, padx=5, pady=5)
        label.pack(side=LEFT)
        entry.pack(side=RIGHT, expand=YES, fill=X)
        entries.append(entry)
    return entries

"""
清空协议编辑器的当前值
:param entries: 协议字段编辑框列表
:return: None
"""
def clear_protocol_editor(entries):
    for entry in entries:
        # 如果有只读Entry，也要清空它的当前值
        state = entry['state']
        entry['state'] = 'normal'
        entry.delete(0, END)
        entry['state'] = state

"""
创建发送按钮和重置按钮
:param root: 编辑编辑区
:return: 发送按钮和清空按钮
"""
def create_bottom_buttons(root):
    bottom_buttons = Frame(root)
    send_packet_button = Button(bottom_buttons, width=20, text="发送")
    default_packet_button = Button(bottom_buttons, width=20, text="默认值")
    reset_button = Button(bottom_buttons, width=20, text="重置")
    bottom_buttons.pack(side=BOTTOM, fill=X, padx=5, pady=5)
    send_packet_button.grid(row=0, column=0, padx=5, pady=5)
    default_packet_button.grid(row=0, column=1, padx=2, pady=5)
    reset_button.grid(row=0, column=2, padx=5, pady=5)
    bottom_buttons.columnconfigure(0, weight=1)
    bottom_buttons.columnconfigure(1, weight=1)
    bottom_buttons.columnconfigure(2, weight=1)
    return send_packet_button, reset_button, default_packet_button

"""
创建MAC帧编辑器
:return: None
"""
def create_mac_sender():
    # MAC帧编辑区
    mac_fields = '源MAC地址：', '目标MAC地址：', '协议类型：'
    entries = create_protocol_editor(protocol_editor_panedwindow, mac_fields)
    send_packet_button, reset_button, default_packet_button = create_bottom_buttons(protocol_editor_panedwindow)
    # 为"回车键"的Press事件编写事件响应代码，发送MAC帧
    tk.bind('<Return>', (lambda event: send_mac_frame(entries, send_packet_button)))  # <Return>代表回车键
    # 为"发送"按钮的单击事件编写事件响应代码，发送MAC帧
    # <Button-1>代表鼠标左键单击
    send_packet_button.bind('<Button-1>', (lambda event: send_mac_frame(entries, send_packet_button)))  
    # 为"清空"按钮的单击事件编写事件响应代码，清空协议字段编辑框
    reset_button.bind('<Button-1>', (lambda event: clear_protocol_editor(entries)))
    # 为"默认值"按钮的单击事件编写事件响应代码，在协议字段编辑框填入MAC帧字段的默认值
    default_packet_button.bind('<Button-1>', (lambda event: create_default_mac_frame(entries)))

"""
在协议字段编辑框中填入默认MAC帧的字段值
:param entries: 协议字段编辑框列表
:return: None
"""
def create_default_mac_frame(entries):
    clear_protocol_editor(entries)
    default_mac_frame = Ether()
    entries[0].insert(0, default_mac_frame.src)
    entries[1].insert(0, default_mac_frame.dst)
    entries[2].insert(0, hex(default_mac_frame.type))

"""
发送MAC帧
:param send_packet_button: MAC帧发送按钮
:param entries:协议字段编辑框列表
:return: None
"""
def send_mac_frame(entries, send_packet_button):
    if send_packet_button['text'] == '发送':
        mac_src = entries[0].get()
        mac_dst = entries[1].get()
        mac_type = int(entries[2].get(), 16)
        packet_to_send = Ether(src=mac_src, dst=mac_dst, type=mac_type)
        packet_to_send.show()
                
        # 开一个线程用于连续发送数据包
        t = threading.Thread(target=send_packet, args=(packet_to_send,))
        t.setDaemon(True)
        t.start()
        
        # 使协议导航树不可用
        toggle_protocols_tree_state()
        send_packet_button['text'] = '停止'
    else:
        # 终止数据包发送线程
        stop_sending.set()
        # 恢复协议导航树可用
        toggle_protocols_tree_state()
        send_packet_button['text'] = '发送'

"""
创建ARP报文编辑器
:return: None
"""
def create_arp_sender():
    # ARP报文编辑区
    arp_fields = '硬件类型：', '协议类型：', '硬件地址长度：', '协议地址长度：', '操作码：', '源MAC地址：', '源IP地址：', '目标MAC地址：', '目标IP地址：'
    entries = create_protocol_editor(protocol_editor_panedwindow, arp_fields)
    send_packet_button, reset_button, default_packet_button = create_bottom_buttons(protocol_editor_panedwindow)
    # 为"回车键"的Press事件编写事件响应代码，发送ARP报文
    tk.bind('<Return>', (lambda event: send_arp_packet(entries, send_packet_button)))  # <Return>代表回车键
    # 为"发送"按钮的单击事件编写事件响应代码，发送ARP报文
    send_packet_button.bind('<Button-1>', (lambda event: send_arp_packet(entries, send_packet_button)))  
    # <Button-1>代表鼠标左键单击
    # 为"清空"按钮的单击事件编写事件响应代码，清空协议字段编辑框
    reset_button.bind('<Button-1>', (lambda event: clear_protocol_editor(entries)))
    # 为"默认值"按钮的单击事件编写事件响应代码，在协议字段编辑框填入ARP报文字段的默认值
    default_packet_button.bind('<Button-1>', (lambda event: create_default_arp_packet(entries)))

"""
在协议字段编辑框中填入默认ARP报文的字段值
:param entries: 协议字段编辑框列表
:return: None
"""
def create_default_arp_packet(entries):
    clear_protocol_editor(entries)
    default_arp_packet = ARP()
    entries[0].insert(0, default_arp_packet.hwtype)
    entries[1].insert(0, hex(default_arp_packet.ptype))
    entries[2].insert(0, default_arp_packet.hwlen)
    entries[3].insert(0, default_arp_packet.plen)
    entries[4].insert(0, default_arp_packet.op)
    entries[5].insert(0, default_arp_packet.hwsrc)
    entries[6].insert(0, default_arp_packet.psrc)
    entries[7].insert(0, default_arp_packet.hwdst)
    # 目标IP地址设成本地默认网关
    entries[8].insert(0, default_dst)

"""
发送ARP报文
:param send_packet_button: ARP报文发送按钮
:param entries:协议字段编辑框列表
:return: None
"""
def send_arp_packet(entries, send_packet_button):
    if send_packet_button['text'] == '发送':
        arp_hwtype = int(entries[0].get())
        arp_ptype = int(entries[1].get(), 16)
        arp_hwlen = int(entries[2].get())
        arp_plen = int(entries[3].get())
        arp_op = int(entries[4].get())
        arp_hwsrc = entries[5].get()
        arp_psrc = entries[6].get()
        arp_hwdst = entries[7].get()
        arp_pdst = entries[8].get()
        packet_to_send = ARP(hwtype=arp_hwtype, ptype=arp_ptype, hwlen=arp_hwlen, plen=arp_plen,op=arp_op, hwsrc=arp_hwsrc, psrc=arp_psrc, hwdst=arp_hwdst, pdst=arp_pdst)
        packet_to_send.show()
        # 开一个线程用于连续发送数据包
        t = threading.Thread(target=send_packet, args=(packet_to_send,))
        t.setDaemon(True)
        t.start()
        # 使协议导航树不可用
        toggle_protocols_tree_state()
        send_packet_button['text'] = '停止'
    else:
        # 终止数据包发送线程
        stop_sending.set()
        # 恢复协议导航树可用
        toggle_protocols_tree_state()
        send_packet_button['text'] = '发送'

"""
创建ICMP报文编辑器
:return: None
"""
def create_icmp_sender():
    # ICMP报文编辑区
    icmp_fields = 'ICMP类型：', 'ICMP校验和：', '协议版本：', '分片ID：', '分片标志位：', '分片偏移：', '生存时间：', 'IP校验和：', '源IP地址：', '目的IP地址：'
    entries = create_protocol_editor(protocol_editor_panedwindow, icmp_fields)
    send_packet_button, reset_button, default_packet_button = create_bottom_buttons(protocol_editor_panedwindow)
    # 为"回车键"的Press事件编写事件响应代码，发送ICMP报文
    tk.bind('<Return>', (lambda event: send_icmp_packet(entries, send_packet_button)))  # <Return>代表回车键
    # 为"发送"按钮的单击事件编写事件响应代码，发送ICMP报文
    send_packet_button.bind('<Button-1>', (lambda event: send_icmp_packet(entries, send_packet_button)))  
    # <Button-1>代表鼠标左键单击
    # 为"清空"按钮的单击事件编写事件响应代码，清空协议字段编辑框
    reset_button.bind('<Button-1>', (lambda event: clear_protocol_editor(entries)))
    # 为"默认值"按钮的单击事件编写事件响应代码，在协议字段编辑框填入ARP报文字段的默认值
    default_packet_button.bind('<Button-1>', (lambda event: create_default_icmp_packet(entries)))

"""
在协议字段编辑框中填入默认ICMP报文的字段值
:param entries: 协议字段编辑框列表
:return: None
"""
def create_default_icmp_packet(entries):
    clear_protocol_editor(entries)
    default_icmp_packet = IP()/ICMP()
    entries[0].insert(0, int(default_icmp_packet.type))
    entries[1].insert(0, str(default_icmp_packet[ICMP].chksum))
    entries[2].insert(0, int(default_icmp_packet.version))
    entries[3].insert(0, int(default_icmp_packet.id))
    entries[4].insert(0, int(default_icmp_packet.flags))
    entries[5].insert(0, int(default_icmp_packet.frag))
    entries[6].insert(0, int(default_icmp_packet.ttl))
    entries[7].insert(0, str(default_icmp_packet[IP].chksum))
    entries[8].insert(0, default_icmp_packet.src)
    entries[9].insert(0, default_dst)
    

"""
发送ICMP报文
:param send_packet_button: ICMP报文发送按钮
:param entries:协议字段编辑框列表
:return: None
"""
def send_icmp_packet(entries, send_packet_button):
    if send_packet_button['text'] == '发送':
        
        icmp_type = int(entries[0].get())
        ip_version = int(entries[2].get())
        ip_id = int(entries[3].get())
        ip_flags = int(entries[4].get())
        ip_frag = int(entries[5].get())
        ip_ttl = int(entries[6].get())
        ip_src = entries[8].get()
        ip_dst = entries[9].get()
        
        packet_to_send = IP()/ICMP()
        
        packet_to_send.type=icmp_type
        packet_to_send.version=ip_version
        packet_to_send.id=ip_id
        packet_to_send.flags=ip_flags
        packet_to_send.frag=ip_frag
        packet_to_send.ttl=ip_ttl
        packet_to_send.src=ip_src
        packet_to_send.dst=ip_dst
        
        # 获得数据包的二进制值
        pkg_raw = raw(packet_to_send)
        # 构造数据包，自动计算校验和
        packet_to_send = IP(pkg_raw)
        # 去除数据包的IP首部，并构建ICMP对象，这样可以获得ICMP的校验和
        pkg_icmp = pkg_raw[20:]
        pkg_icmp = ICMP(pkg_icmp)
        
        entries[1].delete(0, END)
        entries[1].insert(0, hex(pkg_icmp.chksum))
        entries[7].delete(0, END)
        entries[7].insert(0, hex(packet_to_send.chksum))
        
        packet_to_send.show()
        # 开一个线程用于连续发送数据包
        t = threading.Thread(target=send_packet, args=(packet_to_send,))
        t.setDaemon(True)
        t.start()
        # 使协议导航树不可用
        toggle_protocols_tree_state()
        send_packet_button['text'] = '停止'
    else:
        # 终止数据包发送线程
        stop_sending.set()
        # 恢复协议导航树可用
        toggle_protocols_tree_state()
        send_packet_button['text'] = '发送'

"""
创建IP报文编辑器
:return: None
"""
def create_ip_sender():
    # IP报文编辑区
    ip_fields = '协议版本：', '分片ID：', '分片标志位：', '分片偏移：', '生存时间(TTL)：', '协议类型：', 'IP首部校验和：', '源IP地址', '目的IP地址'
    entries = create_protocol_editor(protocol_editor_panedwindow, ip_fields)
    send_packet_button, reset_button, default_packet_button = create_bottom_buttons(protocol_editor_panedwindow)
    # 为"回车键"的Press事件编写事件响应代码，发送IP报文
    tk.bind('<Return>', (lambda event: send_ip_packet(entries, send_packet_button)))  # <Return>代表回车键
    # 为"发送"按钮的单击事件编写事件响应代码，发送IP报文
    send_packet_button.bind('<Button-1>', (lambda event: send_ip_packet(entries, send_packet_button)))  
    # <Button-1>代表鼠标左键单击
    # 为"清空"按钮的单击事件编写事件响应代码，清空协议字段编辑框
    reset_button.bind('<Button-1>', (lambda event: clear_protocol_editor(entries)))
    # 为"默认值"按钮的单击事件编写事件响应代码，在协议字段编辑框填入IP报文字段的默认值
    default_packet_button.bind('<Button-1>', (lambda event: create_default_ip_packet(entries)))

"""
在协议字段编辑框中填入默认IP报文的字段值
:param entries: 协议字段编辑框列表
:return: None
"""
def create_default_ip_packet(entries):
    clear_protocol_editor(entries)
    default_ip_packet = IP()
    entries[0].insert(0, int(default_ip_packet.version))
    entries[1].insert(0, int(default_ip_packet.id))
    entries[2].insert(0, int(default_ip_packet.flags))
    entries[3].insert(0, int(default_ip_packet.frag))
    entries[4].insert(0, int(default_ip_packet.ttl))
    entries[5].insert(0, int(default_ip_packet.proto))
    entries[6].insert(0, str(default_ip_packet.chksum))
    entries[7].insert(0, default_ip_packet.src)
    entries[8].insert(0, default_dst)
    
"""
发送IP报文
:param send_packet_button: IP报文发送按钮
:param entries:协议字段编辑框列表
:return: None
"""
def send_ip_packet(entries, send_packet_button):
    if send_packet_button['text'] == '发送':
        ip_version = int(entries[0].get())
        ip_id = int(entries[1].get())
        ip_flags = int(entries[2].get())
        ip_frag = int(entries[3].get())
        ip_ttl = int(entries[4].get())
        ip_src = entries[7].get()
        ip_dst = entries[8].get()
        
        packet_to_send = IP()
        packet_to_send.version=ip_version
        packet_to_send.id=ip_id
        packet_to_send.flags=ip_flags
        packet_to_send.frag=ip_frag
        packet_to_send.ttl=ip_ttl
        packet_to_send.src=ip_src
        packet_to_send.dst=ip_dst
        packet_to_send = IP(raw(packet_to_send))

        entries[6].delete(0, END)
        entries[6].insert(0, hex(packet_to_send.chksum))
                
        packet_to_send.show()

        # 开一个线程用于连续发送数据包
        t = threading.Thread(target=send_packet, args=(packet_to_send,))
        t.setDaemon(True)
        t.start()
        # 使协议导航树不可用
        toggle_protocols_tree_state()
        send_packet_button['text'] = '停止'
    else:
        # 终止数据包发送线程
        stop_sending.set()
        # 恢复协议导航树可用
        toggle_protocols_tree_state()
        send_packet_button['text'] = '发送'

"""
创建TCP报文编辑器
:return: None
"""
def create_tcp_sender():
    # TCP报文编辑区
    tcp_fields = '源端口：', '目的端口：', '序列号：', '确认号：', '数据偏移：', '标志：', '窗口大小：', 'TCP校验和：', '协议版本：', '服务类型：', '分片ID：', '分片标志位：', '分片偏移：', '生存时间(TTL)：', 'IP首部校验和：', '源IP地址', '目的IP地址'
    entries = create_protocol_editor(protocol_editor_panedwindow, tcp_fields)
    send_packet_button, reset_button, default_packet_button = create_bottom_buttons(protocol_editor_panedwindow)
    # 为"回车键"的Press事件编写事件响应代码，发送TCP报文
    tk.bind('<Return>', (lambda event: send_tcp_packet(entries, send_packet_button)))  
    # <Return>代表回车键
    # 为"发送"按钮的单击事件编写事件响应代码，发送TCP报文
    send_packet_button.bind('<Button-1>', (lambda event: send_tcp_packet(entries, send_packet_button)))  # <Button-1>代表鼠标左键单击
    # 为"清空"按钮的单击事件编写事件响应代码，清空协议字段编辑框
    reset_button.bind('<Button-1>', (lambda event: clear_protocol_editor(entries)))
    # 为"默认值"按钮的单击事件编写事件响应代码，在协议字段编辑框填入TCP报文字段的默认值
    default_packet_button.bind('<Button-1>', (lambda event: create_default_tcp_packet(entries)))

"""
在协议字段编辑框中填入默认TCP报文的字段值
:param entries: 协议字段编辑框列表
:return: None
"""
def create_default_tcp_packet(entries):
    clear_protocol_editor(entries)
    default_tcp_packet = IP()/TCP()
    entries[0].insert(0, int(default_tcp_packet.sport))
    entries[1].insert(0, int(default_tcp_packet.dport))
    entries[2].insert(0, int(default_tcp_packet.seq))
    entries[3].insert(0, int(default_tcp_packet.ack))
    entries[4].insert(0, str(default_tcp_packet.dataofs))
    entries[5].insert(0, 'S')
    entries[6].insert(0, int(default_tcp_packet.window))
    entries[7].insert(0, str(default_tcp_packet[TCP].chksum))
    
    entries[8].insert(0, int(default_tcp_packet.version))
    entries[9].insert(0, str(default_tcp_packet.tos))
    entries[10].insert(0, int(default_tcp_packet.id))
    entries[11].insert(0, int(default_tcp_packet.flags))
    entries[12].insert(0, int(default_tcp_packet.frag))
    entries[13].insert(0, int(default_tcp_packet.ttl))
    entries[14].insert(0, str(default_tcp_packet[IP].chksum))
    entries[15].insert(0, default_tcp_packet.src)
    entries[16].insert(0, default_dst)

"""
发送TCP报文
:param send_packet_button: TCP报文发送按钮
:param entries:协议字段编辑框列表
:return: None
"""
def send_tcp_packet(entries, send_packet_button):
    if send_packet_button['text'] == '发送':
        tcp_sport = int(entries[0].get())
        tcp_dport = int(entries[1].get())
        tcp_seq = int(entries[2].get())
        tcp_ack = int(entries[3].get())
        if entries[4].get() != 'None':
            tcp_dataofs = int(entries[4].get())
        tcp_flags = str(entries[5].get())
        tcp_window = int(entries[6].get())
        
        ip_version = int(entries[8].get())
        ip_tos = int(entries[9].get())
        ip_id = int(entries[10].get())
        ip_flags = int(entries[11].get())
        ip_frag = int(entries[12].get())
        ip_ttl = int(entries[13].get())
        ip_src = entries[15].get()
        ip_dst = entries[16].get()
    
        tcp = TCP()
        tcp.sport=tcp_sport
        tcp.dport=tcp_dport
        tcp.seq=tcp_seq
        tcp.ack=tcp_ack
        if entries[4].get() != 'None':
            tcp.dataofs=tcp_dataofs
        tcp.flags=tcp_flags
        tcp.window=tcp_window
                
        ip = IP()
        ip.version=ip_version
        ip.tos=ip_tos
        ip.id=ip_id
        ip.flags=ip_flags
        ip.frag=ip_frag
        ip.ttl=ip_ttl
        ip.src=ip_src
        ip.dst=ip_dst
        
        # 获得待发送数据包的二进制原始值
        pkg_raw = raw(ip/tcp)
        # 构建发送数据包
        packet_to_send = IP(pkg_raw)
        # 去除数据包的IP首部，并构建TCP对象，这样可以获得TCP的校验和
        tcp_raw = pkg_raw[20:]
        pkg_tcp = TCP(tcp_raw)
        
        # TCP校验和
        entries[7].delete(0, END)
        entries[7].insert(0, hex(pkg_tcp.chksum))
        # IP首部校验和
        entries[14].delete(0, END)
        entries[14].insert(0, hex(packet_to_send.chksum))
        
        packet_to_send.show()
                
        # 开一个线程用于连续发送数据包
        t = threading.Thread(target=send_packet, args=(packet_to_send,))
        t.setDaemon(True)
        t.start()
        # 使协议导航树不可用
        toggle_protocols_tree_state()
        send_packet_button['text'] = '停止'
    else:
        # 终止数据包发送线程
        stop_sending.set()
        # 恢复协议导航树可用
        toggle_protocols_tree_state()
        send_packet_button['text'] = '发送'

"""
创建UDP报文编辑器
:return: None
"""
def create_udp_sender():
    # UDP报文编辑区
    udp_fields = '源端口：', '目的端口：', '校验和：', '协议版本：', '分片ID：', '分片标志位：', '分片偏移：', '生存时间：', '校验和：', '源IP地址', '目的IP地址'
    entries = create_protocol_editor(protocol_editor_panedwindow, udp_fields)
    send_packet_button, reset_button, default_packet_button = create_bottom_buttons(protocol_editor_panedwindow)
    # 为"回车键"的Press事件编写事件响应代码，发送UDP报文
    tk.bind('<Return>', (lambda event: send_udp_packet(entries, send_packet_button)))  
    # <Return>代表回车键
    # 为"发送"按钮的单击事件编写事件响应代码，发送UDP报文
    send_packet_button.bind('<Button-1>', (lambda event: send_udp_packet(entries, send_packet_button)))  # <Button-1>代表鼠标左键单击
    # 为"清空"按钮的单击事件编写事件响应代码，清空协议字段编辑框
    reset_button.bind('<Button-1>', (lambda event: clear_protocol_editor(entries)))
    # 为"默认值"按钮的单击事件编写事件响应代码，在协议字段编辑框填入UDP报文字段的默认值
    default_packet_button.bind('<Button-1>', (lambda event: create_default_udp_packet(entries)))

"""
在协议字段编辑框中填入默认UDP报文的字段值
:param entries: 协议字段编辑框列表
:return: None
"""
def create_default_udp_packet(entries):
    clear_protocol_editor(entries)
    default_udp_packet = IP()/UDP()
    entries[0].insert(0, int(default_udp_packet.sport))
    entries[1].insert(0, int(default_udp_packet.dport))
    entries[2].insert(0, str(default_udp_packet[UDP].chksum))
    
    entries[3].insert(0, int(default_udp_packet.version))
    entries[4].insert(0, int(default_udp_packet.id))
    entries[5].insert(0, int(default_udp_packet.flags))
    entries[6].insert(0, int(default_udp_packet.frag))
    entries[7].insert(0, int(default_udp_packet.ttl))
    entries[8].insert(0, str(default_udp_packet[IP].chksum))
    entries[9].insert(0, default_udp_packet.src)
    entries[10].insert(0, default_dst)

"""
发送UDP报文
:param send_packet_button: UDP报文发送按钮
:param entries:协议字段编辑框列表
:return: None
"""
def send_udp_packet(entries, send_packet_button):
    if send_packet_button['text'] == '发送':
        udp_sport = int(entries[0].get())
        udp_dport = int(entries[1].get())
        
        ip_version = int(entries[3].get())
        ip_id = int(entries[4].get())
        ip_flags = int(entries[5].get())
        ip_frag = int(entries[6].get())
        ip_ttl = int(entries[7].get())
        ip_src = entries[9].get()
        ip_dst = entries[10].get()
    
        packet_to_send = IP()/UDP()
        
        packet_to_send.sport=udp_sport
        packet_to_send.dport=udp_dport
        packet_to_send.version=ip_version
        packet_to_send.id=ip_id
        packet_to_send.flags=ip_flags
        packet_to_send.frag=ip_frag
        packet_to_send.ttl=ip_ttl
        packet_to_send.src=ip_src
        packet_to_send.dst=ip_dst
        
        # 获得数据包的二进制值
        pkg_raw = raw(packet_to_send)
        # 构造数据包，自动计算校验和
        packet_to_send = IP(pkg_raw)
        # 去除数据包的IP首部，并构建UDP对象，这样可以获得UDP的校验和
        pkg_udp = pkg_raw[20:]
        pkg_udp = UDP(pkg_udp)
        
        entries[2].delete(0, END)
        entries[2].insert(0, hex(pkg_udp.chksum))
        entries[8].delete(0, END)
        entries[8].insert(0, hex(packet_to_send.chksum))
        
        # 开一个线程用于连续发送数据包
        t = threading.Thread(target=send_packet, args=(packet_to_send,))
        t.setDaemon(True)
        t.start()
        # 使协议导航树不可用
        toggle_protocols_tree_state()
        send_packet_button['text'] = '停止'
    else:
        # 终止数据包发送线程
        stop_sending.set()
        # 恢复协议导航树可用
        toggle_protocols_tree_state()
        send_packet_button['text'] = '发送'


"""
创建HTTP报文编辑器
:return: None
"""
def create_http_sender():
    # HTTP报文编辑区
    http_fields = 'HTTP报头：', '源端口：', '目的端口：', '源IP地址：', '目的IP地址：'
    entries = create_protocol_editor(protocol_editor_panedwindow, http_fields)
    send_packet_button, reset_button, default_packet_button = create_bottom_buttons(protocol_editor_panedwindow)
    # 为"回车键"的Press事件编写事件响应代码，发送HTTP报文
    tk.bind('<Return>', (lambda event: send_http_packet(entries, send_packet_button)))  
    # <Return>代表回车键
    # 为"发送"按钮的单击事件编写事件响应代码，发送HTTP报文
    send_packet_button.bind('<Button-1>', (lambda event: send_http_packet(entries, send_packet_button)))  
    # <Button-1>代表鼠标左键单击
    # 为"清空"按钮的单击事件编写事件响应代码，清空协议字段编辑框
    reset_button.bind('<Button-1>', (lambda event: clear_protocol_editor(entries)))
    # 为"默认值"按钮的单击事件编写事件响应代码，在协议字段编辑框填入HTTP报文字段的默认值
    default_packet_button.bind('<Button-1>', (lambda event: create_default_http_packet(entries)))

"""
在协议字段编辑框中填入默认HTTP报文的字段值
:param entries: 协议字段编辑框列表
:return: None
"""
def create_default_http_packet(entries):
    clear_protocol_editor(entries)
    default_http_packet = TCP()/IP()
    
    entries[0].insert(0, "GET / HTTP/1.1\r\n")
    entries[1].insert(0, default_http_packet.sport)
    entries[2].insert(0, default_http_packet.dport)
    entries[3].insert(0, default_http_packet.src)
    entries[4].insert(0, default_dst)

"""
发送HTTP报文
:param send_packet_button: HTTP报文发送按钮
:param entries:协议字段编辑框列表
:return: None
"""
def send_http_packet(entries, send_packet_button):
    if send_packet_button['text'] == '发送':
        http_options = entries[0].get()
        http_sport = int(entries[1].get())
        http_dport = int(entries[2].get())
        http_src = entries[3].get()
        http_dst = entries[4].get()
    
        tcp = TCP()
        tcp.sport=http_sport
        tcp.dport=http_dport
        
        ip = IP()
        ip.src=http_src
        ip.dst=http_dst
        packet_to_send = ip/tcp/http_options
                
        # 开一个线程用于连续发送数据报文
        t = threading.Thread(target=send_packet, args=(packet_to_send,))
        t.setDaemon(True)
        t.start()
        # 使协议导航树不可用
        toggle_protocols_tree_state()
        send_packet_button['text'] = '停止'
    else:
        # 终止数据包发送线程
        stop_sending.set()
        # 恢复协议导航树可用
        toggle_protocols_tree_state()
        send_packet_button['text'] = '发送'

"""
用于发送数据包的线程函数，持续发送数据包
:type packet_to_send: 待发送的数据包
"""
def send_packet(packet_to_send):
    # 对发送的数据包次数进行计数，用于计算发送速度
    n = 0
    stop_sending.clear()
    # 待发送数据包的长度（用于计算发送速度）
    packet_size = len(packet_to_send)
    # 推导数据包的协议类型
    proto_names = ['TCP', 'UDP', 'ICMP', 'IP', 'ARP', 'Ether', 'Unknown']
    packet_proto = ''
    for pn in proto_names:
        if pn in packet_to_send:
            packet_proto = pn
            break
    # 开始发送时间点
    begin_time = datetime.now()
    while not stop_sending.is_set():
        if isinstance(packet_to_send, Ether):
            # verbose=0,不在控制回显'Sent 1 packets'.
            sendp(packet_to_send, verbose=0)
        else:
            send(packet_to_send, verbose=0)
        n += 1
        end_time = datetime.now()
        total_bytes = packet_size * n
        bytes_per_second = total_bytes / ((end_time - begin_time).total_seconds()) / 1024
        status_bar.set('已经发送了%d个%s数据包, 已经发送了%d个字节，发送速率: %0.2fkB/s',
                                             n, packet_proto, total_bytes, bytes_per_second)


def create_welcome_page(root):
    welcome_string = '巨丑的封面\n计算机网络课程设计\n协议编辑器\n学号：150341221\n姓名：路伟饶'
    Label(root, justify=CENTER, padx=10, pady=150, text=welcome_string,font=('隶书', '30', 'bold')).pack()

if __name__ == '__main__':
    # 创建协议导航树并放到左右分隔窗体的左侧
    main_panedwindow.add(create_protocols_tree())
    # 将协议编辑区窗体放到左右分隔窗体的右侧
    main_panedwindow.add(protocol_editor_panedwindow)
    # 创建欢迎界面
    create_welcome_page(protocol_editor_panedwindow)
    main_panedwindow.pack(fill=BOTH, expand=1)
    # 启动消息处理
    tk.mainloop()
  