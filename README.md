# Non-markovian Graph Edit Networks

This repository focuses on Non-markovian Graph Edit Networks. In more detail, we attempt to extend the Graph Edit Networks proposed by Paassen et al. by the methods that have been proposed by Pareja et al. to account for non-Markovian systems. For further details on the methodology and the results see the report [here](https://github.com/jatlantic/GNN/blob/main/Non-Markovian%20GEN.pdf).

## Datasets

We used two different temporal network datasets to test the graph edit networks in a non-markovian setting:

1. The first dataset where the non-markovian graph edit network approach was tested on is the High-energy physics theory citation network which can be found [here](https://snap.stanford.edu/data/cit-HepTh.html).
2. The second dataset we used is called CollegeMsg temporal network and refers to private messages sent online in a college context. The data can be found [here](https://snap.stanford.edu/data/CollegeMsg.html).


## Getting Started

All information to run the code yourself is contained in the `HEP_CollegeMSG_Testing.ipynb` and `graph_dynamical_systems.ipynb` files where each cell can be run from top to bottom. 

## Main References

1. Dataset

J. Leskovec, J. Kleinberg and C. Faloutsos. Graphs over Time: Densification Laws, Shrinking Diameters and Possible Explanations. ACM SIGKDD International Conference on Knowledge Discovery and Data Mining (KDD), 2005.
J. Gehrke, P. Ginsparg, J. M. Kleinberg. Overview of the 2003 KDD Cup. SIGKDD Explorations 5(2): 149-151, 2003.

2. Dataset

Pietro Panzarasa, Tore Opsahl, and Kathleen M. Carley. "Patterns and dynamics of users' behavior and interaction: Network analysis of an online community." Journal of the American Society for Information Science and Technology 60.5 (2009): 911-932.

3. Graph Edit Networks

Paassen, B., Grattarola, D., Zambon, D., Alippi, C. & Hammer, B. E. Graph edit networks. in International conference on learning representations (2021).

4. EvolveGCN

Pareja, A. et al. Evolvegcn: Evolving graph convolutional networks for dynamic graphs. in vol. 34 5363–5370 (2020).

