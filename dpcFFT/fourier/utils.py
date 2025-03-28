"""
Fourier utils
"""

import numpy as np
from scipy.spatial import KDTree
from scipy.spatial import ConvexHull
from shapely.geometry import Point, Polygon


def compute_coordinate_system(points):
    mean = np.mean(points, axis=0)
    points = points - mean
    covariance = np.cov(points.T)
    vals, vectors = np.linalg.eigh(covariance)
    idx = np.argsort(vals)[::-1]
    vectors = vectors[:, idx]
    return vectors.T, mean


def plane_projection(points, size):
    min_ = np.min(points, axis=0)
    max_ = np.max(points, axis=0)
    grid_x, grid_y = np.linspace(min_[0], max_[0], size), np.linspace(
        min_[1], max_[1], size
    )
    sampled_points = []

    grid = np.zeros((size, size))

    tree = KDTree(points[:, :2])
    for i, x in enumerate(grid_x):
        for j, y in enumerate(grid_y):
            _, idx = tree.query([x, y])
            sampled_points.append(points[idx, :2])
            grid[i, j] = points[idx, 2]

    sampled_points = np.asarray(sampled_points)

    return grid, grid_x, grid_y, sampled_points


def fourier_filter(height, filter_func, *args):
    fft_height = np.fft.fft2(height)
    fft_shifted = np.fft.fftshift(fft_height)

    rows, cols = fft_shifted.shape
    center_row, center_col = rows // 2, cols // 2

    mask = np.zeros((rows, cols))

    for i in range(rows):
        for j in range(cols):
            distance = np.sqrt((i - center_row) ** 2 + (j - center_col) ** 2)
            if distance <= 20:
                mask[i, j] = 1

    fft_filtered = fft_shifted * mask

    fft_inverse_shifted = np.fft.ifftshift(fft_filtered)  # Shift back
    filtered_heights = np.fft.ifft2(fft_inverse_shifted).real

    return filtered_heights


def gaussian_f(grid, sigma):
    x = np.linspace(-0.5, 0.5, grid.shape[0])
    y = np.linspace(-0.5, 0.5, grid.shape[1])
    X, Y = np.meshgrid(x, y)
    return np.exp(-(X**2 + Y**2) / (2 * sigma**2))


def grid_to_points(grid, grid_x, grid_y):
    X, Y = np.meshgrid(grid_x, grid_y, indexing="ij")
    points = np.column_stack([X.flatten(), Y.flatten(), grid.flatten()])
    return points


def filter_fourier_artifacts(sampled_points, grid_points):
    hull = ConvexHull(sampled_points)
    hull_points = sampled_points[hull.vertices]
    polygon = Polygon(hull_points)

    filtered_points = []
    for point in grid_points:
        point_ = Point(*point[:2])
        if polygon.contains(point_):
            filtered_points.append(point)
    return np.asarray(filtered_points)


def icp(points, target, max_iter=50, max_error=1e-6):
    target_tree = KDTree(target)
    prev_error = float("inf")
    R_total = np.eye(3)
    t_total = np.zeros(3)

    for _ in range(max_iter):
        _, idx = target_tree.query(points)
        closest_points = target[idx]

        mu_src = np.mean(points, axis=0)
        mu_target = np.mean(closest_points, axis=0)

        src_centered = points - mu_src
        target_centered = closest_points - mu_target

        H = src_centered.T @ target_centered
        U, _, Vt = np.linalg.svd(H)
        R = Vt.T @ U.T

        if np.linalg.det(R) < 0:
            Vt[-1, :] *= -1
            R = Vt.T @ U.T

        t = mu_target - R @ mu_src
        points = (R @ points.T).T + t
        R_total = R @ R_total
        t_total = R @ t_total + t

        mean_error = np.mean(np.linalg.norm(closest_points - points, axis=1))
        if abs(prev_error - mean_error) < max_error:
            break
        prev_error = mean_error

    return points, R_total, t_total
