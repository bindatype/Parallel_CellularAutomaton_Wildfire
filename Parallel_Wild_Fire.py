# Wild Fire Simulation Using Cellular Automaton and Parallel Computing
# Designed By Xiaochi (George) Li
# Final Project for High Performance Computing and Parallel Computing
# Data Science @ George Washington University
# May. 2018

# Algorithm based on this paper:A cellular automata model for forest fire spread prediction: The case
# of the wildfire that swept through Spetses Island in 1990
# Author: A. Alexandridis a, D. Vakalis b, C.I. Siettos c,*, G.V. Bafas a

# import os
import sys
import time
import math
import random
import copy
import itertools
# from tqdm import tqdm

from mpi4py import MPI
comm = MPI.COMM_WORLD
size = comm.Get_size()
rank = comm.Get_rank()
stat = MPI.Status()

try:
    import numpy as np
    import matplotlib.pyplot as plt
    from matplotlib import cm
    from matplotlib import animation as animation
    visual = True
except:
    print("Error: This code need numpy and matplot to visualize!")
    visual = False



if visual:
    fig = plt.figure()


# ------------ Change the code below here for different initial environment ---------

# -------------Quick Change Begin-------------------------
# number of rows and columns of full grid and the generations
n_row_total = 300
n_col = 300
generation = 300

# the possibility a cell will continue to burn in next time step
# change the value to change the boundary of fire
p_continue_burn = 0.5

# Quick switch for factors in the model, turn on: True, turn off: False
wind = False
vegetation = False
density = False
altitude = False

# ------------- Quick Change End---------------------------------------

n_row = n_row_total // size + 2

thetas = [[45, 0, 45],
          [90, 0, 90],
          [135, 180, 135]]


def init_vegetation():
    veg_matrix = [[0 for col in range(n_col)] for row in range(n_row)]
    if vegetation == False:  # turn off vegetation
        for i in range(n_row):
            for j in range(n_col):
                veg_matrix[i][j] = 1
    else:
        for i in range(n_row):
            for j in range(n_col):
                if j <= n_col//3 : veg_matrix[i][j] = 1
                elif j <= n_col*2//3: veg_matrix[i][j] = 2
                else: veg_matrix[i][j] = 3
    return veg_matrix


def init_density():
    den_matrix = [[0 for col in range(n_col)] for row in range(n_row)]
    if density == False:  # turn off density
        for i in range(n_row):
            for j in range(n_col):
                den_matrix[i][j] = 1
    else:
        for i in range(n_row):
            for j in range(n_col):
                if j <= n_col//3: den_matrix[i][j] = 1
                elif j <= n_col*2//3: den_matrix[i][j] = 2
                else: den_matrix[i][j] = 3
    return den_matrix


def init_altitude():
    alt_matrix = [[0 for col in range(n_col)] for row in range(n_row)]
    if altitude == False:  # turn off altitude
        for i in range(n_row):
            for j in range(n_col):
                alt_matrix[i][j] = 1
    else:
        for i in range(n_row):
            for j in range(n_col):
                alt_matrix[i][j] = j
    return alt_matrix


def init_forest():
    forest = [[1 for col in range(n_col)] for row in range(n_row)]

    for i in range(n_row):
        if i == 0 or i == n_row - 1:  # [parallel] sub grid initial exchange row is one
            continue
        for j in range(n_col):
            if j == 0 or j == n_col - 1:  # [parallel] sub grid initial margin column is one
                continue
            forest[i][j] = 2
    ignite_col = int(n_col//2)
    ignite_row = int(n_row//2)
    if rank == size // 2:  # [parallel] sub grid only ignite center sub grid
        for row in range(ignite_row-1, ignite_row+1):
            for col in range(ignite_col-1,ignite_col+1):
                forest[row][col] = 3
    # forest[ignite_row-2:ignite_row+2][ignite_col-2:ignite_col+2] = 3
    return forest

# ------------------ Do not change anything below this line ----------------


# ------------------ Parallel Function ----------------
def msg_up(sub_grid):
    # Sends and Receives rows with Rank+1
    comm.send(sub_grid[n_row-2], dest=rank+1)
    sub_grid[n_row-1] = comm.recv(source=rank+1)
    return 0


def msg_down(sub_grid):
    # Sends and Receives rows with Rank-1
    comm.send(sub_grid[1], dest=rank-1)
    sub_grid[0] = comm.recv(source=rank-1)
    return 0


# ------------------ Parallel Function End ----------------
def colormap(title, array):
    np_array = np.array(array)
    plt.imshow(np_array, interpolation="none", cmap=cm.plasma)
    plt.title(title)
    plt.show()


def print_forest(title,forest):
    print (title)
    for i in range(len(forest)):
        for j in range(n_col):
            if not isinstance(title, int):
                sys.stdout.write(str(forest[i][j]))
            elif forest[i][j] == 1:
                sys.stdout.write("\033[1;34;40m 1\033[0m")  # blue for not burnable
            elif forest[i][j] == 2:
                sys.stdout.write("\033[1;32;40m 2\033[0m")  # green for burnable
            elif forest[i][j] == 3:
                sys.stdout.write("\033[1;31;40m 3\033[0m")  # red for burning
            else:
                sys.stdout.write("\033[1;30;40m 4\033[0m")  # black for burned down
        sys.stdout.write("\n")
    print ("--------------------")


def tg(x):
    return math.degrees(math.atan(x))


def get_slope(altitude_matrix):
    slope_matrix = [[0 for col in range(n_col)] for row in range(n_row)]
    for row in range(n_row):
        for col in range(n_col):
            sub_slope_matrix = [[0,0,0],[0,0,0],[0,0,0]]
            if row == 0 or row == n_row-1 or col == 0 or col == n_col-1:  # margin is flat
                slope_matrix[row][col] = sub_slope_matrix
                continue
            current_altitude = altitude_matrix[row][col]
            sub_slope_matrix[0][0] = tg((current_altitude - altitude_matrix[row-1][col-1])/1.414)
            sub_slope_matrix[0][1] = tg(current_altitude - altitude_matrix[row-1][col])
            sub_slope_matrix[0][2] = tg((current_altitude - altitude_matrix[row-1][col+1])/1.414)
            sub_slope_matrix[1][0] = tg(current_altitude - altitude_matrix[row][col-1])
            sub_slope_matrix[1][1] = 0
            sub_slope_matrix[1][2] = tg(current_altitude - altitude_matrix[row][col+1])
            sub_slope_matrix[2][0] = tg((current_altitude - altitude_matrix[row+1][col-1])/1.414)
            sub_slope_matrix[2][1] = tg(current_altitude - altitude_matrix[row+1][col])
            sub_slope_matrix[2][2] = tg((current_altitude - altitude_matrix[row+1][col+1])/1.414)
            slope_matrix[row][col] = sub_slope_matrix
    return slope_matrix


def calc_pw(theta):
    c_1 = 0.045
    c_2 = 0.131
    V = 10
    t = math.radians(theta)
    ft = math.exp(V*c_2*(math.cos(t)-1))
    return math.exp(c_1*V)*ft


def get_wind():

    wind_matrix = [[0 for col in [0,1,2]] for row in [0,1,2]]

    for row in [0,1,2]:
        for col in [0,1,2]:
            wind_matrix[row][col] = calc_pw(thetas[row][col])
    wind_matrix[1][1] = 0

    if wind == False:  # turn off wind
        wind_matrix = [[1 for col in [0,1,2]] for row in [0,1,2]]
    return wind_matrix


def burn_or_not_burn(abs_row,abs_col,neighbour_matrix):
    p_veg = {1:-0.3,2:0,3:0.4}[vegetation_matrix[abs_row][abs_col]]
    p_den = {1:-0.4,2:0,3:0.3}[density_matrix[abs_row][abs_col]]
    p_h = 0.58
    a = 0.078

    for row in [0,1,2]:
        for col in [0,1,2]:
            if neighbour_matrix[row][col] == 3: # we only care there is a neighbour that is burning
                # print(row,col)
                slope = slope_matrix[abs_row][abs_col][row][col]
                p_slope = math.exp(a * slope)
                p_wind = wind_matrix[row][col]
                p_burn = p_h * (1 + p_veg) * (1 + p_den) * p_wind * p_slope
                if p_burn > random.random():
                    return 3  #start burning

    return 2 # not burning


def update_forest(old_forest):
    result_forest = [[1 for i in range(n_col)] for j in range(n_row)]
    for row in range(1, n_row-1):
        for col in range(1, n_col-1):

            if old_forest[row][col] == 1 or old_forest[row][col] == 4:
                result_forest[row][col] = old_forest[row][col]  # no fuel or burnt down
            if old_forest[row][col] == 3:
                if random.random() < p_continue_burn:
                    result_forest[row][col] = 3  # We can change here to control the burning time
                else:
                    result_forest[row][col] = 4
            if old_forest[row][col] == 2:
                neighbours = [[row_vec[col_vec] for col_vec in range(col-1, col+2)]
                              for row_vec in old_forest[row-1:row+2]]
                # print(neighbours)
                result_forest[row][col] = burn_or_not_burn(row, col, neighbours)
    return result_forest


# start simulation
vegetation_matrix = init_vegetation()
density_matrix = init_density()
altitude_matrix = init_altitude()
wind_matrix = get_wind()
slope_matrix = get_slope(altitude_matrix)
sub_forest = init_forest()  # [parallel] each worker has their own sub grid

# draw initial condition in colour map
# TODO: need to change for parallel version
if rank == 0:
    if visual:
        colormap("Vegetation Map", vegetation_matrix)
        colormap("Density Map", density_matrix)
        colormap("Altitude Map", altitude_matrix)
    else:

        print_forest("Vegetation Map", vegetation_matrix)
        print_forest("Density Map", density_matrix)
        print_forest("Altitude Map", altitude_matrix)
    print("This is the wind matrix:")
    for row in wind_matrix:
        print(row)
time.sleep(1)


ims = []
# for i in tqdm(range(generation)):
for i in range(generation):  # tqdm will damage the visualization in Terminal

    sub_forest = copy.deepcopy(update_forest(sub_forest))
    # [parallel] message passing function
    if rank == 0:
        msg_up(sub_forest)
    elif rank == size - 1:
        msg_down(sub_forest)
    else:
        msg_up(sub_forest)
        msg_down(sub_forest)

    # transform the list to np array so we can use np.vstack later
    # np_temp_grid = np.array(sub_forest[1:n_row - 1])
    # temp_grid = comm.gather(np_temp_grid, root=0)
    temp_grid = comm.gather(sub_forest[1:n_row - 1], root=0)

    # [parallel] only worker 0 do the visualize

    if rank == 0:

        list_forest = list(itertools.chain.from_iterable(temp_grid))

        if visual:
            print(i, "/", generation)
            new_forest = np.vstack(list_forest)
            im = plt.imshow(new_forest, animated=True, interpolation="none", cmap=cm.plasma)
            # plt.title(i)
            ims.append([im])
            # colormap(i,new_forest)
        else:
            # os.system("clear")
            time.sleep(1)
            print("-----------Generation:", i, "---------------")
            # list_forest = new_forest.tolist()
            # print (list_forest)
            print_forest(i,list_forest)
            # for components_of_forest in list_forest:
            #     print_forest(i, components_of_forest)
            # print(new_forest)


if visual and rank == 0:
    ani = animation.ArtistAnimation(fig, ims, interval=25, blit=True,repeat_delay=500)
    # ani.save('animate_life.html')
    plt.show()