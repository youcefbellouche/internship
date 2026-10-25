import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import Polygon

# Configure figure dimensions for IEEE single-column (width 8.4 in, height 11.2 in, 300 dpi)
fig, ax = plt.subplots(figsize=(8.4, 11.2), dpi=300)
ax.set_xlim(0, 14.2)
ax.set_ylim(0, 16.2)
ax.axis('off')

# Publication-grade color palette
c_ue_border   = '#1b4f72'  # Deep Slate Blue
c_ue_hdr      = '#eaf2f8'  # Soft Ice Blue
c_bridge_bdr  = '#145a32'  # Forest Green
c_bridge_hdr  = '#eafaf1'  # Soft Mint
c_ran_border  = '#78281f'  # Dark Crimson
c_ran_hdr     = '#fdf2e9'  # Warm Apricot
c_if_border   = '#2c3e50'  # Charcoal
c_if_hdr      = '#f4f6f7'  # Cool Gray
box_bg        = '#ffffff'
c_text        = '#111111'
c_subtext     = '#444444'

font_sec   = {'fontsize': 10.5, 'fontweight': 'bold', 'family': 'sans-serif'}
font_class = {'fontsize': 9.4, 'fontweight': 'bold', 'family': 'sans-serif'}
font_ste   = {'fontsize': 7.8, 'fontstyle': 'italic', 'family': 'sans-serif'}
font_body  = {'fontsize': 8.2, 'family': 'sans-serif'}
font_tag   = {'fontsize': 7.6, 'fontweight': 'bold', 'family': 'sans-serif'}

# 1. Subsystem Framing Bands
rect_ue = patches.FancyBboxPatch((0.4, 6.7), 13.4, 9.1, boxstyle="round,pad=0.15",
                                 edgecolor='#90caf9', facecolor='#fbfdff', linewidth=1.2, linestyle=':')
ax.add_patch(rect_ue)
ax.text(0.65, 15.45, "UE Subsystem (srsUE Monolithic Cross-Stack Linking)", **font_sec, color='#154360')

rect_ran = patches.FancyBboxPatch((0.4, 0.5), 13.4, 5.8, boxstyle="round,pad=0.15",
                                  edgecolor='#ffcc80', facecolor='#fffdfc', linewidth=1.2, linestyle=':')
ax.add_patch(rect_ran)
ax.text(0.65, 5.95, "RAN Subsystem (oCUDU Disaggregated F1-U Anchoring)", **font_sec, color='#78281f')

# 2. Precision Class Box Renderer (Mathematically Guaranteed No-Overlap)
def draw_class_box(ax, x, top_y, w, class_name, stereotype=None, attributes=None, methods=None, 
                   header_bg='#ffffff', border_col='#000000'):
    line_h = 0.33
    hdr_h = 0.72 if stereotype else 0.52
    
    attr_count = len(attributes) if attributes else 0
    meth_count = len(methods) if methods else 0
    
    attr_h = (attr_count * line_h + 0.18) if attr_count > 0 else 0.28
    meth_h = (meth_count * line_h + 0.18) if meth_count > 0 else 0.28
    
    total_h = hdr_h + attr_h + meth_h
    bot_y = top_y - total_h
    
    # Outer rectangle
    outer = patches.Rectangle((x, bot_y), w, total_h, edgecolor=border_col, facecolor=box_bg, linewidth=1.2, zorder=2)
    ax.add_patch(outer)
    
    # Header compartment
    hdr_y = top_y - hdr_h
    hdr_rect = patches.Rectangle((x, hdr_y), w, hdr_h, edgecolor=border_col, facecolor=header_bg, linewidth=1.2, zorder=3)
    ax.add_patch(hdr_rect)
    
    if stereotype:
        ax.text(x + w/2, top_y - 0.22, stereotype, ha='center', va='center', **font_ste, color=c_subtext, zorder=4)
        ax.text(x + w/2, top_y - 0.50, class_name, ha='center', va='center', **font_class, color=border_col, zorder=4)
    else:
        ax.text(x + w/2, top_y - (hdr_h/2), class_name, ha='center', va='center', **font_class, color=border_col, zorder=4)
        
    ax.plot([x, x + w], [hdr_y, hdr_y], color=border_col, lw=1.2, zorder=4)
    
    # Attributes compartment
    div_attr_y = hdr_y - attr_h
    if attributes:
        cur_y = hdr_y - 0.22
        for attr in attributes:
            ax.text(x + 0.20, cur_y, attr, ha='left', va='center', **font_body, color=c_text, zorder=4)
            cur_y -= line_h
    ax.plot([x, x + w], [div_attr_y, div_attr_y], color=border_col, lw=1.0, zorder=4)
    
    # Methods compartment
    if methods:
        cur_y = div_attr_y - 0.22
        for m in methods:
            ax.text(x + 0.20, cur_y, m, ha='left', va='center', **font_body, color=c_text, zorder=4)
            cur_y -= line_h
            
    anchors = {
        'top': (x + w/2, top_y),
        'bottom': (x + w/2, bot_y),
        'left': (x, (top_y + bot_y)/2),
        'right': (x + w, (top_y + bot_y)/2),
        'mid_x': x + w/2,
        'mid_y': (top_y + bot_y)/2,
        'top_y': top_y,
        'bot_y': bot_y,
        'left_x': x,
        'right_x': x + w,
        'w': w,
        'h': total_h
    }
    return anchors

# UML 2.0 Realization (Dashed line with hollow closed triangle)
def draw_realization(ax, p_start, p_end):
    sx, sy = p_start
    ex, ey = p_end
    import math
    dx, dy = ex - sx, ey - sy
    dist = math.hypot(dx, dy)
    ux, uy = dx/dist, dy/dist
    head_len = 0.28
    head_w = 0.17
    
    base_x = ex - ux * head_len
    base_y = ey - uy * head_len
    perp_x = -uy * head_w
    perp_y = ux * head_w
    
    ax.plot([sx, base_x], [sy, base_y], color='#111111', lw=1.2, linestyle='--', zorder=5)
    tri = Polygon([[ex, ey], [base_x + perp_x, base_y + perp_y], [base_x - perp_x, base_y - perp_y]],
                  closed=True, edgecolor='#111111', facecolor='#ffffff', lw=1.2, zorder=6)
    ax.add_patch(tri)

# UML 2.0 Composition (Solid black diamond at start)
def draw_composition(ax, p_start, p_end, label=None):
    sx, sy = p_start
    ex, ey = p_end
    import math
    dx, dy = ex - sx, ey - sy
    dist = math.hypot(dx, dy)
    ux, uy = dx/dist, dy/dist
    d_len = 0.28
    d_w = 0.15
    
    tip_x = sx + ux * d_len
    tip_y = sy + uy * d_len
    perp_x = -uy * d_w
    perp_y = ux * d_w
    
    diamond = Polygon([[sx, sy],
                       [sx + ux*(d_len/2) + perp_x, sy + uy*(d_len/2) + perp_y],
                       [tip_x, tip_y],
                       [sx + ux*(d_len/2) - perp_x, sy + uy*(d_len/2) - perp_y]],
                      closed=True, edgecolor='#111111', facecolor='#111111', lw=1.2, zorder=6)
    ax.add_patch(diamond)
    ax.plot([tip_x, ex], [tip_y, ey], color='#111111', lw=1.2, zorder=5)
    if label:
        ax.text((sx+ex)/2 + 0.18, (sy+ey)/2, label, **font_tag, color='#154360', ha='left', va='center', zorder=7)

# UML 2.0 Directed Association (Solid line with open arrowhead)
def draw_association(ax, p_start, p_end, zorder=5):
    arrow = patches.FancyArrowPatch(p_start, p_end, arrowstyle="-|>", mutation_scale=11,
                                    color='#111111', lw=1.2, zorder=zorder)
    ax.add_patch(arrow)

# ----------------- 3. CLASS DEFINITIONS & LAYOUT -----------------
# Optimized box width: 4.4 units
# Left Column:  x = 0.8, Width = 4.4 (right edge = 5.2)
# Right Column: x = 9.0, Width = 4.4 (left edge = 9.0)
# Massive central gap: 9.0 - 5.2 = 3.8 units (Guaranteed ZERO collisions!)

# Class 1: srsran::pdcp (Top Left)
a_pdcp = draw_class_box(ax, x=0.8, top_y=14.8, w=4.4,
                        class_name="srsran::pdcp",
                        stereotype="<<Master Node Layer 2>>",
                        attributes=["- split_bridge : rlc_split_bridge",
                                    "- rlc_sn : rlc_interface_pdcp*"],
                        methods=["+ init(config) : void",
                                 "+ write_sdu(lcid, sdu) : void",
                                 "+ set_rlc_sn(rlc*) : void"],
                        header_bg=c_ue_hdr, border_col=c_ue_border)

# Interface: rlc_interface_pdcp (Top Right)
a_if = draw_class_box(ax, x=9.0, top_y=14.8, w=4.4,
                      class_name="rlc_interface_pdcp",
                      stereotype="<<interface>>",
                      attributes=None,
                      methods=["+ write_sdu(lcid, sdu) = 0",
                               "+ discard_sdu(lcid, sn) = 0",
                               "+ sdu_queue_is_full(lcid) = 0"],
                      header_bg=c_if_hdr, border_col=c_if_border)

# Class 2: rlc_split_bridge (Middle Left)
a_bridge = draw_class_box(ax, x=0.8, top_y=11.1, w=4.4,
                          class_name="rlc_split_bridge",
                          stereotype="<<bridge, multiplexer>>",
                          attributes=["- ratio_mn, ratio_sn : uint32_t",
                                      "- duplication_mode : bool",
                                      "+ mn_rlc : rlc_interface_pdcp*",
                                      "+ sn_rlc : rlc_interface_pdcp*"],
                          methods=["+ write_sdu(lcid, sdu) : void",
                                   "+ check_runtime_ratio() : void",
                                   "+ apply_ratio_str(str) : void",
                                   "+ sdu_queue_is_full(lcid) : bool"],
                          header_bg=c_bridge_hdr, border_col=c_bridge_bdr)

# Class 3: srsran::rlc (Middle Right)
a_rlc = draw_class_box(ax, x=9.0, top_y=11.4, w=4.4,
                       class_name="srsran::rlc",
                       stereotype="<<RLC Leg (TN / NTN)>>",
                       attributes=["- tx_sdu_queue : buffer_t",
                                   "- rb_is_um : bool",
                                   "+ lcid : uint32_t"],
                       methods=["+ write_sdu(lcid, sdu) : void",
                                "+ set_pdcp(pdcp*) : void",
                                "+ sdu_queue_is_full(lcid) : bool",
                                "+ discard_sdu(lcid, sn) : void"],
                       header_bg=c_ue_hdr, border_col=c_ue_border)

# ----------------- UE RELATIONSHIPS -----------------

# 1. Composition: pdcp embeds rlc_split_bridge (Vertical, left column)
draw_composition(ax, a_pdcp['bottom'], a_bridge['top'], label="embeds")
ax.text(a_pdcp['mid_x'] + 0.16, a_pdcp['bot_y'] - 0.20, "1", **font_tag, color='#333333', ha='left', va='top')
ax.text(a_bridge['mid_x'] + 0.16, a_bridge['top_y'] + 0.20, "1", **font_tag, color='#333333', ha='left', va='bottom')

# 2. Realization: srsran::rlc implements rlc_interface_pdcp (Vertical, right column)
draw_realization(ax, a_rlc['top'], a_if['bottom'])

# 3. Association: Uplink SDU dispatch from Bridge to RLC entities (Horizontal across gap)
y_ul = 8.5
draw_association(ax, (a_bridge['right_x'], y_ul), (a_rlc['left_x'], y_ul), zorder=5)
ax.text(7.1, y_ul + 0.45, "+mn_rlc / +sn_rlc\n(UL SDU dispatch)", **font_tag, color='#154360', ha='center', va='bottom',
        bbox=dict(boxstyle='round,pad=0.22', facecolor='#ffffff', edgecolor='#aed6f1', lw=0.7), zorder=7)
ax.text(a_bridge['right_x'] + 0.18, y_ul - 0.18, "1", **font_tag, color='#444444', ha='left', va='top')
ax.text(a_rlc['left_x'] - 0.18, y_ul - 0.18, "1..2", **font_tag, color='#444444', ha='right', va='top')

# 4. Realization: rlc_split_bridge implements rlc_interface_pdcp (Orthogonal stepped path)
# Path: (5.2, 10.2) -> (5.8, 10.2) -> (5.8, 13.8) -> (9.0, 13.8)
ax.plot([a_bridge['right_x'], 5.8], [10.2, 10.2], color='#111111', lw=1.2, linestyle='--', zorder=5)
ax.plot([5.8, 5.8], [10.2, 13.8], color='#111111', lw=1.2, linestyle='--', zorder=5)
draw_realization(ax, (5.8, 13.8), (a_if['left_x'], 13.8))

# 5. Association: Downlink SDU return delivery from RLC to Master PDCP (Orthogonal stepped path)
# Path: (9.0, 10.7) -> (8.4, 10.7) -> (8.4, 12.3) -> (5.2, 12.3)
ax.plot([a_rlc['left_x'], 8.4], [10.7, 10.7], color='#111111', lw=1.2, zorder=8)
ax.plot([8.4, 8.4], [10.7, 12.3], color='#111111', lw=1.2, zorder=8)
# At crossing point (5.8, 12.3), place a white bridge mask behind the solid line
ax.plot([5.65, 5.95], [12.3, 12.3], color='#ffffff', lw=4.0, zorder=7)
# Draw horizontal arrow entering PDCP right edge
draw_association(ax, (8.4, 12.3), (a_pdcp['right_x'], 12.3), zorder=8)
# Place label above the horizontal segment in the wide 2.6-unit gap between x=5.8 and x=8.4
ax.text(7.1, 12.65, "+pdcp_mn (DL)", **font_tag, color='#154360', ha='center', va='bottom',
        bbox=dict(boxstyle='round,pad=0.2', facecolor='#ffffff', edgecolor='#aed6f1', lw=0.6), zorder=9)


# ----------------- 4. RAN SUBSYSTEM (oCUDU CU-UP) -----------------

# Class 4: cu_up_bearer_context (Bottom Left)
a_cu = draw_class_box(ax, x=0.8, top_y=5.4, w=4.4,
                      class_name="cu_up_bearer_context",
                      stereotype="<<CU-UP Anchor, 3GPP Rel-17>>",
                      attributes=["- terminal_imsi : std::string",
                                  "- drb_id : uint32_t",
                                  "- cu_pdcp : cu_up_pdcp_entity",
                                  "- f1u_tunnels[2] : f1u_socket*"],
                      methods=["+ dispatch_downlink(sdu) : void",
                               "+ process_uplink(gtp_pdu) : void",
                               "+ configure_split_policy() : void"],
                      header_bg=c_ran_hdr, border_col=c_ran_border)

# Class 5: f1u_tunnel_endpoint (Bottom Right)
a_f1u = draw_class_box(ax, x=9.0, top_y=5.4, w=4.4,
                       class_name="f1u_tunnel_endpoint",
                       stereotype="<<GTP-U / UDP Socket>>",
                       attributes=["- du_ip : 127.0.10.2 / 127.0.10.3",
                                   "- teid : uint32_t",
                                   "- target_du : DU_1 | DU_2",
                                   "- backoff_timer_ms : uint32_t"],
                       methods=["+ send_gtp_packet(pdu) : void",
                                "+ recv_gtp_packet() : buffer_t",
                                "+ notify_backpressure() : void"],
                       header_bg=c_ran_hdr, border_col=c_ran_border)

# Association: CU-UP Bearer Context anchors 2 F1-U Tunnels (DU1 and DU2)
y_ran = 3.65
draw_association(ax, (a_cu['right_x'], y_ran), (a_f1u['left_x'], y_ran), zorder=5)

# Label placed cleanly above the arrow with va='bottom' so it NEVER touches the line or borders
ax.text(7.1, y_ran + 0.45, "Dual F1-U Sockets\n(DU1: TN | DU2: NTN)", 
        **font_tag, color='#78281f', ha='center', va='bottom',
        bbox=dict(boxstyle='round,pad=0.25', facecolor='#ffffff', edgecolor='#ffcc80', lw=0.7), zorder=7)

# Multiplicity annotations placed cleanly below the arrow line
ax.text(a_cu['right_x'] + 0.18, y_ran - 0.18, "1", **font_tag, color='#555555', ha='left', va='top')
ax.text(a_f1u['left_x'] - 0.18, y_ran - 0.18, "2", **font_tag, color='#555555', ha='right', va='top')

plt.tight_layout()
plt.savefig("Adaptive Cross-Layer Recovery for PDCP Split Bearers in space-terrestrial Multi-Connectivity/Sections/Architectural Description/Images/uml_class_diagram.png",
            dpi=300, bbox_inches='tight')
plt.savefig("Adaptive Cross-Layer Recovery for PDCP Split Bearers in space-terrestrial Multi-Connectivity/Sections/Architectural Description/Images/uml_class_diagram.jpg",
            dpi=300, bbox_inches='tight')
print("Successfully generated pixel-perfect UML 2.0 diagram!")
