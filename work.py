import matplotlib.pyplot as plt
import numpy as np

# Given values
a = 3  # side BC opposite angle A=35°
A_deg, B_deg, C_deg = 35, 85, 60

# Convert angles to radians
A = np.deg2rad(A_deg)
B = np.deg2rad(B_deg)
C = np.deg2rad(C_deg)

# Compute sides b and c via Law of Sines
b = a * np.sin(B) / np.sin(A)
c = a * np.sin(C) / np.sin(A)

# Place A at (0,0), B at (c,0)
A_pt = np.array([0.0, 0.0])
B_pt = np.array([c, 0.0])

# Compute C using side b and angle at A
dx = b * np.cos(A)
dy = b * np.sin(A)
C_pt = np.array([dx, dy])

# Plot triangle
plt.figure(figsize=(6,6))
X = [A_pt[0], B_pt[0], C_pt[0], A_pt[0]]
Y = [A_pt[1], B_pt[1], C_pt[1], A_pt[1]]
plt.plot(X, Y, '-o', color='blue')

# Label vertices
plt.text(A_pt[0]-0.1, A_pt[1]-0.1, 'A (0,0)', fontsize=12)
plt.text(B_pt[0]+0.05, B_pt[1]-0.1, f'B ({c:.2f},0)', fontsize=12)
plt.text(C_pt[0]+0.05, C_pt[1]+0.05, f'C ({dx:.2f},{dy:.2f})', fontsize=12)

# Label side lengths
mid_BC = (B_pt + C_pt) / 2
mid_CA = (C_pt + A_pt) / 2
mid_AB = (A_pt + B_pt) / 2
plt.text(mid_BC[0], mid_BC[1]-0.1, f'a = {a}', color='red')
plt.text(mid_CA[0]-0.4, mid_CA[1]+0.1, f'b = {b:.2f}', color='red')
plt.text(mid_AB[0], mid_AB[1]-0.1, f'c = {c:.2f}', color='red')

# Draw and label angles with small arcs
arc_radius = 0.3

# Angle at A
theta = np.linspace(0, A, 30)
plt.plot(arc_radius*np.cos(theta), arc_radius*np.sin(theta), color='green')
plt.text(arc_radius*0.7, arc_radius*0.3, f'{A_deg}°', color='green')

# Angle at B
phi = np.linspace(np.pi, np.pi - B, 30)
tmpx = B_pt[0] + arc_radius*np.cos(phi)
tmpy = B_pt[1] + arc_radius*np.sin(phi)
plt.plot(tmpx, tmpy, color='green')
plt.text(B_pt[0] - arc_radius*0.6, arc_radius*0.3, f'{B_deg}°', color='green')

# Angle at C
psi = np.linspace(-np.pi/2 + C, -np.pi/2, 30)
tmpx2 = C_pt[0] + arc_radius*np.cos(psi)
tmpy2 = C_pt[1] + arc_radius*np.sin(psi)
plt.plot(tmpx2, tmpy2, color='green')
plt.text(C_pt[0] - arc_radius, C_pt[1] - 0.1, f'{C_deg}°', color='green')

plt.axis('equal')
plt.axis('off')
plt.show()