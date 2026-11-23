"""Plan A* routes on a Scene with the real observer visibility layer.

Glue between the scene format, the visibility module and A*:

    slope           = slope of the ground terrain (scene.terrain), in degrees
    blocked         = scene.obstacle_mask()  (buildings and vehicles are never entered)
    visibility_cost = visibility.visibility_cost(scene.surface(), scene.observers, ..., obstacle_mask=blocked)
    route           = astar(slope, start, goal, visibility_cost=..., w_vis=w_vis, blocked=blocked)

Slope comes from the ground terrain, not from the surface, so building walls do not show up as cliffs;
buildings are handled by `blocked` instead. For real scenes whose terrain is already a surface model
(terrain_is_surface = true, e.g. antalya_dem) the slope still contains building edges; that is a limitation
of the data, not of this module.

The visibility layer is the slow part (seconds at 10 m, see visibility/observer.py) and does not depend on
w_vis, so compute it once with scene_visibility() and pass it to plan_route() for every w_vis value.
"""
import numpy as np

from guvenli_rota.routing.astar import DEFAULT_MAX_SLOPE_DEG, astar
from guvenli_rota.visibility.observer import visibility_cost

DEFAULT_TARGET_HEIGHT_M = 1.7  # height of the person being looked at


def terrain_slope_deg(scene):
    """(H, W) slope of the ground terrain in degrees (central differences, as in scripts/build_grid.py)."""
    gy, gx = np.gradient(scene.terrain.astype(np.float64), scene.resolution)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def scene_visibility(scene, time="day", weights=None, target_height=DEFAULT_TARGET_HEIGHT_M):
    """(H, W) number of observers (or their weighted sum) that see each cell; 0 on obstacle cells."""
    return visibility_cost(scene.surface(), scene.observers, scene.resolution, scene.meta["origin"],
                           time=time, weights=weights, target_height=target_height,
                           obstacle_mask=scene.obstacle_mask())


def plan_route(scene, start_xy, goal_xy, w_vis=0.0, time="day", visibility=None,
               max_slope_deg=DEFAULT_MAX_SLOPE_DEG):
    """A* route between two world points (x, y) of the scene. Returns an AStarResult (path in cells).

    w_vis = 0 gives the shortest slope-weighted route that avoids obstacles; a larger w_vis trades length
    for staying out of sight. `visibility` is an optional precomputed scene_visibility(scene, time); when it
    is not given it is computed here, also for w_vis = 0, so the result's visibility_cost and visible_cells
    always describe how visible the route is.
    """
    if visibility is None:
        visibility = scene_visibility(scene, time)
    return astar(terrain_slope_deg(scene), scene.world_to_cell(*start_xy), scene.world_to_cell(*goal_xy),
                 cell_size=scene.resolution, max_slope_deg=max_slope_deg, visibility_cost=visibility,
                 w_vis=w_vis, blocked=scene.obstacle_mask())


def plan_task(scene, task, w_vis=0.0, visibility=None, max_slope_deg=DEFAULT_MAX_SLOPE_DEG):
    """plan_route for one entry of tasks.json (uses its start, goal and time)."""
    return plan_route(scene, task["start"], task["goal"], w_vis=w_vis, time=task.get("time", "day"),
                      visibility=visibility, max_slope_deg=max_slope_deg)
