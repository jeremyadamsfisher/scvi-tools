use_cuda = True
from scvi.harmonization.utils_chenling import get_matrix_from_dir
from scvi.dataset.pbmc import PbmcDataset
from scvi.harmonization.utils_chenling import assign_label
import numpy as np
from scipy.stats import entropy
from sklearn.neighbors import NearestNeighbors

from scvi.dataset.dataset import GeneExpressionDataset
from scvi.harmonization.utils_chenling import run_model
from copy import deepcopy

import matplotlib
matplotlib.rcParams['pdf.fonttype'] = 42
matplotlib.rcParams['ps.fonttype'] = 42
import matplotlib.pyplot as plt
import seaborn as sns

from scvi.metrics.clustering import entropy_batch_mixing
from sklearn.manifold import TSNE
from sklearn.neighbors import KNeighborsClassifier

plotname = 'NoOverlap'

dataset1 = PbmcDataset(filter_out_de_genes=False)
dataset1.update_cells(dataset1.batch_indices.ravel()==0)
dataset1.subsample_genes(dataset1.nb_genes)

count, geneid, cellid = get_matrix_from_dir('cite')
count = count.T.tocsr()
seurat = np.genfromtxt('../cite/cite.seurat.labels', dtype='str', delimiter=',')
cellid = np.asarray([x.split('-')[0] for x in cellid])
labels_map = [0, 0, 1, 2, 3, 4, 5, 6]
labels = seurat[1:, 4]
cell_type = ['CD4 T cells', 'NK cells', 'CD14+ Monocytes', 'B cells','CD8 T cells', 'FCGR3A+ Monocytes', 'Other']
dataset2 = assign_label(cellid, geneid, labels_map, count, cell_type, seurat)
set(dataset2.cell_types).intersection(set(dataset2.cell_types))

prop2 = dict( zip(dataset2.cell_types[np.unique(dataset2.labels,return_counts=True)[0]],
                  np.unique(dataset2.labels,return_counts=True)[1]/len(dataset2)))

prop =dict(zip(dataset1.cell_types, np.unique(dataset1.labels,return_counts=True)[1]/len(dataset1)))
for i,name in enumerate(list(set(dataset2.cell_types).intersection(set(dataset2.cell_types)))):
    print("%s & %.3f & %.3f\\\\ \n" % (name,prop[name],prop2[name]))


dataset1.subsample_genes(dataset1.nb_genes)
dataset2.subsample_genes(dataset2.nb_genes)


def entropy_from_indices(indices):
    return entropy(np.array(np.unique(indices, return_counts=True)[1].astype(np.int32)))


def entropy_batch_mixing_subsampled(latent, batches, labels, removed_type, sampled_batch=0, n_neighbors=50, n_pools=50, n_samples_per_pool=100):
    X = latent[labels == removed_type,:]
    nbrs = NearestNeighbors(n_neighbors=n_neighbors + 1).fit(latent)
    indices = nbrs.kneighbors(X, return_distance=False)[:, 1:]
    batch_indices = np.vectorize(lambda i: batches[i])(indices)
    entropies = np.apply_along_axis(entropy_from_indices, axis=1, arr=batch_indices)
    if n_pools == 1:
        res = np.mean(entropies)
    else:
        res = np.mean([
            np.mean(entropies[np.random.choice(len(entropies), size=n_samples_per_pool)])
            for _ in range(n_pools)
        ])
    return res

from scvi.metrics.clustering import clustering_scores,select_indices_evenly

f = open('../'+plotname+'/res.txt', "w+")

from scvi.dataset.dataset import SubsetGenes

# scp chenlingantelope@s128.millennium.berkeley.edu:/data/yosef2/users/chenling/harmonization/Seurat_data/PopRemove*

for rmCellTypes in dataset2.cell_types[:6]:
    pbmc = deepcopy(dataset1)
    newCellType = [k for i, k in enumerate(dataset1.cell_types) if k not in [rmCellTypes]]
    pbmc.filter_cell_types(newCellType)
    pbmc2 = deepcopy(dataset2)
    pbmc2.filter_cell_types([rmCellTypes])
    gene_dataset = GeneExpressionDataset.concat_datasets(pbmc, pbmc2)
    pbmc = deepcopy(gene_dataset)
    pbmc.update_cells(pbmc.batch_indices.ravel() == 0)
    pbmc.subsample_genes(pbmc.nb_genes)
    pbmc2 = deepcopy(gene_dataset)
    pbmc2.update_cells(gene_dataset.batch_indices.ravel() == 1)
    pbmc2.subsample_genes(dataset2.nb_genes)
    # latent, batch_indices, labels, keys, stats = run_model(
    #     'writedata', gene_dataset, pbmc, pbmc2,filename=plotname+rmCellTypes.replace(' ',''))
    latent, batch_indices, labels, keys, stats = run_model(
        'readSeurat', gene_dataset, pbmc, pbmc2,filename=plotname+rmCellTypes.replace(' ',''))

    otheridx = np.arange(len(keys))[keys == 'Other'][0]
    latent = latent[labels!=otheridx,:]
    batch_indices = batch_indices[labels!=otheridx]
    labels = labels[labels!=otheridx]
    map = dict(zip(np.unique(labels),np.argsort(np.unique(labels))))
    labels = np.asarray([map[x] for x in labels])
    keys = keys[keys!='Other']

    subsample = select_indices_evenly(np.min(np.unique(batch_indices,return_counts=True)[1]),batch_indices)
    BE = entropy_batch_mixing(latent[subsample,:],batch_indices[subsample],10)
    neigh = KNeighborsClassifier(n_neighbors=10)
    neigh = neigh.fit(latent,labels)
    labels_pred = neigh.predict(latent)
    acc = [np.mean(labels[labels_pred==i]==i) for i in np.unique(labels)]
    res = [BE]+acc
    cell_type = keys[np.unique(labels)]

    f.write('Seurat' + '\t' + rmCellTypes + ("\t%.4f" * 9 + "\t%s"*8 + "\n") % tuple(res+list(cell_type)))

    # colors = sns.color_palette('tab20')
    # sample = select_indices_evenly(2000, labels)
    # latent_s = latent[sample, :]
    # label_s = labels[sample]
    # batch_s = batch_indices[sample]
    # if latent_s.shape[1] != 2:
    #     latent_s = TSNE().fit_transform(latent_s)
    #
    # fig, ax = plt.subplots(figsize=(13, 10))
    # key_order = np.argsort(keys)
    # for i, k in enumerate(key_order):
    #     ax.scatter(latent_s[label_s == k, 0], latent_s[label_s == k, 1], c=colors[i % 20], label=keys[k],
    #                edgecolors='none')
    #     ax.legend(bbox_to_anchor=(1.1, 0.5), borderaxespad=0, fontsize='x-large')
    #
    # fig.tight_layout()
    # plt.savefig('../' + plotname + '/Seurat' + '.' + rmCellTypes.replace(' ', '') + '.labels.png')
    # plt.figure(figsize=(10, 10))
    # plt.scatter(latent_s[:, 0], latent_s[:, 1], c=batch_s, edgecolors='none')
    # plt.axis("off")
    # plt.tight_layout()
    # plt.savefig('../' + plotname + '/Seurat' + '.' + rmCellTypes.replace(' ', '') + '.batchid.png')

    pbmc, pbmc2, gene_dataset = SubsetGenes(pbmc, pbmc2, gene_dataset, plotname+rmCellTypes.replace(' ',''))
    latent, batch_indices, labels, keys, stats = run_model(
        'vae', gene_dataset, pbmc, pbmc2,filename=plotname, rep = rmCellTypes.replace(' ',''))

    otheridx = np.arange(len(keys))[keys == 'Other'][0]
    latent = latent[labels!=otheridx,:]
    batch_indices = batch_indices[labels!=otheridx]
    labels = labels[labels!=otheridx]
    map = dict(zip(np.unique(labels),np.argsort(np.unique(labels))))
    labels = np.asarray([map[x] for x in labels])
    keys = keys[keys!='Other']

    subsample = select_indices_evenly(np.min(np.unique(batch_indices,return_counts=True)[1]),batch_indices)
    BE = entropy_batch_mixing(latent[subsample,:],batch_indices[subsample],10)
    neigh = KNeighborsClassifier(n_neighbors=10)
    neigh = neigh.fit(latent,labels)
    labels_pred = neigh.predict(latent)
    acc = [np.mean(labels[labels_pred==i]==i) for i in np.unique(labels)]
    res = [BE]+acc
    cell_type = keys[np.unique(labels)]

    f.write('vae' + '\t' + rmCellTypes + ("\t%.4f" * 9 + "\t%s"*8 + "\n") % tuple(res+list(cell_type)))


    # colors = sns.color_palette('tab20')
    # sample = select_indices_evenly(2000, labels)
    # latent_s = latent[sample, :]
    # label_s = labels[sample]
    # batch_s = batch_indices[sample]
    # if latent_s.shape[1] != 2:
    #     latent_s = TSNE().fit_transform(latent_s)
    #
    # fig, ax = plt.subplots(figsize=(13, 10))
    # key_order = np.argsort(keys)
    # for i, k in enumerate(key_order):
    #     ax.scatter(latent_s[label_s == k, 0], latent_s[label_s == k, 1], c=colors[i % 20], label=keys[k],
    #                edgecolors='none')
    #     ax.legend(bbox_to_anchor=(1.1, 0.5), borderaxespad=0, fontsize='x-large')
    #
    # fig.tight_layout()
    # plt.savefig('../' +  plotname + '/vae' + '.' + rmCellTypes.replace(' ', '') + '.labels.png')
    # plt.figure(figsize=(10, 10))
    # plt.scatter(latent_s[:, 0], latent_s[:, 1], c=batch_s, edgecolors='none')
    # plt.axis("off")
    # plt.tight_layout()
    # plt.savefig('../' +  plotname + '/vae' + '.' + rmCellTypes.replace(' ', '') + '.batchid.png')

f.close()
