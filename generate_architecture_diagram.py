import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Set high-DPI figure
fig, ax = plt.subplots(figsize=(14, 8), dpi=300)
ax.set_xlim(0, 14)
ax.set_ylim(0, 8.5)
ax.axis('off')

# Font settings
font_title = {'fontsize': 14, 'fontweight': 'bold', 'family': 'sans-serif'}
font_box_header = {'fontsize': 11, 'fontweight': 'bold', 'family': 'sans-serif'}
font_box_text = {'fontsize': 10, 'fontweight': 'bold', 'family': 'sans-serif'}
font_subtext = {'fontsize': 8.5, 'family': 'sans-serif'}
font_label = {'fontsize': 8, 'family': 'sans-serif', 'style': 'italic'}

# Main Title
ax.text(7, 8.2, "5G Standalone Multi-Radio Dual-Connectivity (MR-DC)", 
        ha='center', va='center', fontsize=16, fontweight='bold', family='sans-serif')

# ==============================================================================
# LEFT CONTAINER: Disaggregated gNodeB (oCUDU)
# ==============================================================================
# Outer box
box_gnb = patches.FancyBboxPatch((0.4, 0.4), 6.1, 7.4, boxstyle="round,pad=0.1", 
                                 edgecolor='black', facecolor='#fafafa', linewidth=1.5)
ax.add_patch(box_gnb)
ax.text(3.45, 7.55, "Disaggregated gNodeB (oCUDU)", ha='center', va='center', **font_box_header)

# CU Row (Top)
# O-CU-CP
cu_cp = patches.FancyBboxPatch((0.8, 5.7), 2.4, 1.3, boxstyle="round,pad=0.05",
                              edgecolor='black', facecolor='white', linewidth=1.2)
ax.add_patch(cu_cp)
ax.text(2.0, 6.5, "O-CU-CP", ha='center', va='center', **font_box_text)
ax.text(2.0, 6.1, "(Control Plane)", ha='center', va='center', **font_subtext)

# O-CU-UP
cu_up = patches.FancyBboxPatch((3.7, 5.7), 2.4, 1.3, boxstyle="round,pad=0.05",
                              edgecolor='black', facecolor='white', linewidth=1.2)
ax.add_patch(cu_up)
ax.text(4.9, 6.5, "O-CU-UP", ha='center', va='center', **font_box_text)
ax.text(4.9, 6.1, "(User Plane)", ha='center', va='center', **font_subtext)

# E1 Interface between CU-CP and CU-UP
ax.annotate("", xy=(3.7, 6.35), xytext=(3.2, 6.35),
            arrowprops=dict(arrowstyle="<->", color='black', lw=1.2))
ax.text(3.45, 6.6, "E1 (SCTP)", ha='center', va='center', **font_label)

# DU Row (Bottom) - Flipped as requested!
# DU1
du1 = patches.FancyBboxPatch((0.8, 1.5), 2.4, 2.0, boxstyle="round,pad=0.05",
                            edgecolor='black', facecolor='white', linewidth=1.2)
ax.add_patch(du1)
ax.text(2.0, 2.8, "DU1", ha='center', va='center', fontsize=12, fontweight='bold')
ax.text(2.0, 2.3, "Distributed Unit 1", ha='center', va='center', **font_subtext)
ax.text(2.0, 1.9, "(Sector 1 / PCI 1)", ha='center', va='center', **font_label)

# DU2
du2 = patches.FancyBboxPatch((3.7, 1.5), 2.4, 2.0, boxstyle="round,pad=0.05",
                            edgecolor='black', facecolor='white', linewidth=1.2)
ax.add_patch(du2)
ax.text(4.9, 2.8, "DU2", ha='center', va='center', fontsize=12, fontweight='bold')
ax.text(4.9, 2.3, "Distributed Unit 2", ha='center', va='center', **font_subtext)
ax.text(4.9, 1.9, "(Sector 2 / PCI 2)", ha='center', va='center', **font_label)

# F1-C Connections (from O-CU-CP to DU1 and DU2)
# CU-CP -> DU1
ax.annotate("", xy=(1.6, 3.5), xytext=(1.6, 5.7),
            arrowprops=dict(arrowstyle="<->", color='#004488', lw=1.3))
ax.text(1.15, 4.6, "F1-C\n(SCTP)", ha='center', va='center', **font_label, color='#004488')

# CU-CP -> DU2
ax.annotate("", xy=(4.2, 3.5), xytext=(2.5, 5.7),
            arrowprops=dict(arrowstyle="<->", color='#004488', lw=1.3, linestyle='dashed'))
ax.text(3.1, 4.8, "F1-C (SCTP)", ha='center', va='center', **font_label, color='#004488', rotation=-40)

# F1-U Connections (from O-CU-UP to DU1 and DU2)
# CU-UP -> DU1
ax.annotate("", xy=(2.4, 3.5), xytext=(4.1, 5.7),
            arrowprops=dict(arrowstyle="<->", color='#bb5500', lw=1.3, linestyle='dashed'))
ax.text(3.5, 4.2, "F1-U (GTP-U)", ha='center', va='center', **font_label, color='#bb5500', rotation=40)

# CU-UP -> DU2
ax.annotate("", xy=(5.3, 3.5), xytext=(5.3, 5.7),
            arrowprops=dict(arrowstyle="<->", color='#bb5500', lw=1.3))
ax.text(5.75, 4.6, "F1-U\n(GTP-U)", ha='center', va='center', **font_label, color='#bb5500')


# ==============================================================================
# RIGHT CONTAINER: Monolithic Dual-Stack UE (srsue)
# ==============================================================================
# Outer box
box_ue = patches.FancyBboxPatch((7.5, 0.4), 6.1, 7.4, boxstyle="round,pad=0.1", 
                                edgecolor='black', facecolor='#fafafa', linewidth=1.5)
ax.add_patch(box_ue)
ax.text(10.55, 7.55, "Monolithic Dual-Stack UE (srsue)", ha='center', va='center', **font_box_header)

# Applications / Upper Layers
app_box = patches.FancyBboxPatch((8.8, 6.7), 3.5, 0.55, boxstyle="round,pad=0.05",
                                edgecolor='black', facecolor='white', linewidth=1.2)
ax.add_patch(app_box)
ax.text(10.55, 6.97, "Upper Layers / Applications (IP/TUN)", ha='center', va='center', **font_subtext)

# Arrow App <-> PDCP
ax.annotate("", xy=(10.55, 6.7), xytext=(10.55, 6.25),
            arrowprops=dict(arrowstyle="<->", color='black', lw=1.2))

# PDCP - Renamed to just "PDCP" as requested!
pdcp_box = patches.FancyBboxPatch((8.3, 5.65), 4.5, 0.6, boxstyle="round,pad=0.05",
                                 edgecolor='#006600', facecolor='#eefbee', linewidth=1.5)
ax.add_patch(pdcp_box)
ax.text(10.55, 5.95, "PDCP", ha='center', va='center', fontsize=12, fontweight='bold', color='#005500')

# Lower Stack Box: Master Cell Group (MCG) on LEFT, Secondary Cell Group (SCG) on RIGHT!
# MCG Box (Left)
mcg_box = patches.FancyBboxPatch((7.8, 0.7), 2.5, 4.2, boxstyle="round,pad=0.05",
                                edgecolor='#225588', facecolor='white', linewidth=1.2)
ax.add_patch(mcg_box)
ax.text(9.05, 4.6, "Master Cell Group (MCG)", ha='center', va='center', fontsize=9.5, fontweight='bold', color='#113366')
ax.text(9.05, 4.3, "[Thread 1 / DU1]", ha='center', va='center', **font_label)

# Layers in MCG
rlc1 = patches.FancyBboxPatch((8.05, 3.2), 2.0, 0.7, boxstyle="round,pad=0.03", edgecolor='black', facecolor='#f0f4f8', lw=1)
ax.add_patch(rlc1)
ax.text(9.05, 3.55, "RLC1", ha='center', va='center', **font_box_text)

mac1 = patches.FancyBboxPatch((8.05, 2.1), 2.0, 0.7, boxstyle="round,pad=0.03", edgecolor='black', facecolor='#f0f4f8', lw=1)
ax.add_patch(mac1)
ax.text(9.05, 2.45, "MAC1", ha='center', va='center', **font_box_text)

phy1 = patches.FancyBboxPatch((8.05, 1.0), 2.0, 0.7, boxstyle="round,pad=0.03", edgecolor='black', facecolor='#f0f4f8', lw=1)
ax.add_patch(phy1)
ax.text(9.05, 1.35, "PHY1", ha='center', va='center', **font_box_text)

# MCG inter-layer arrows
ax.annotate("", xy=(9.05, 3.2), xytext=(9.05, 2.8), arrowprops=dict(arrowstyle="<->", color='black', lw=1))
ax.annotate("", xy=(9.05, 2.1), xytext=(9.05, 1.7), arrowprops=dict(arrowstyle="<->", color='black', lw=1))

# SCG Box (Right)
scg_box = patches.FancyBboxPatch((10.7, 0.7), 2.5, 4.2, boxstyle="round,pad=0.05",
                                edgecolor='#884422', facecolor='white', linewidth=1.2)
ax.add_patch(scg_box)
ax.text(11.95, 4.6, "Secondary Cell Group (SCG)", ha='center', va='center', fontsize=9.5, fontweight='bold', color='#662211')
ax.text(11.95, 4.3, "[Thread 2 / DU2]", ha='center', va='center', **font_label)

# Layers in SCG
rlc2 = patches.FancyBboxPatch((10.95, 3.2), 2.0, 0.7, boxstyle="round,pad=0.03", edgecolor='black', facecolor='#fdf4ef', lw=1)
ax.add_patch(rlc2)
ax.text(11.95, 3.55, "RLC2", ha='center', va='center', **font_box_text)

mac2 = patches.FancyBboxPatch((10.95, 2.1), 2.0, 0.7, boxstyle="round,pad=0.03", edgecolor='black', facecolor='#fdf4ef', lw=1)
ax.add_patch(mac2)
ax.text(11.95, 2.45, "MAC2", ha='center', va='center', **font_box_text)

phy2 = patches.FancyBboxPatch((10.95, 1.0), 2.0, 0.7, boxstyle="round,pad=0.03", edgecolor='black', facecolor='#fdf4ef', lw=1)
ax.add_patch(phy2)
ax.text(11.95, 1.35, "PHY2", ha='center', va='center', **font_box_text)

# SCG inter-layer arrows
ax.annotate("", xy=(11.95, 3.2), xytext=(11.95, 2.8), arrowprops=dict(arrowstyle="<->", color='black', lw=1))
ax.annotate("", xy=(11.95, 2.1), xytext=(11.95, 1.7), arrowprops=dict(arrowstyle="<->", color='black', lw=1))

# In-Memory pointer connections between PDCP and lower stacks
# PDCP to RLC1
ax.annotate("", xy=(9.05, 3.9), xytext=(9.7, 5.65),
            arrowprops=dict(arrowstyle="<->", color='#004488', lw=1.4))
ax.text(8.9, 5.0, "In-memory C++\npointer", ha='center', va='center', **font_label, color='#004488')

# PDCP to RLC2
ax.annotate("", xy=(11.95, 3.9), xytext=(11.4, 5.65),
            arrowprops=dict(arrowstyle="<->", color='#006600', lw=1.4))
ax.text(12.15, 5.0, "In-memory\nrlc_split_bridge", ha='center', va='center', **font_label, color='#006600')

# Save clean plain image
plt.tight_layout()
plt.savefig("Adaptive Cross-Layer Recovery for PDCP Split Bearers in space-terrestrial Multi-Connectivity/Sections/Architectural Description/Images/architecture_diagram.png", 
            dpi=300, bbox_inches='tight')
plt.savefig("Adaptive Cross-Layer Recovery for PDCP Split Bearers in space-terrestrial Multi-Connectivity/Sections/Architectural Description/Images/architecture_diagram.jpg", 
            dpi=300, bbox_inches='tight')
print("Diagram generated successfully!")
