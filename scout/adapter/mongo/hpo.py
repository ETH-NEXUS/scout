# -*- coding: utf-8 -*-
import datetime
import logging
import operator
from bson import ObjectId
from pymongo.errors import DuplicateKeyError, BulkWriteError
import pymongo

from scout.exceptions import IntegrityError

LOG = logging.getLogger(__name__)


class HpoHandler(object):
    def load_hpo_term(self, hpo_obj):
        """Add a hpo object

        Arguments:
            hpo_obj(dict)

        """
        LOG.debug("Loading hpo term %s into database", hpo_obj["_id"])
        try:
            self.hpo_term_collection.insert_one(hpo_obj)
        except DuplicateKeyError as err:
            raise IntegrityError("Hpo term %s already exists in database".format(hpo_obj["_id"]))
        LOG.debug("Hpo term saved")

    def load_hpo_bulk(self, hpo_bulk):
        """Add a hpo object

        Arguments:
            hpo_bulk(list(scout.models.HpoTerm))

        Returns:
            result: pymongo bulkwrite result

        """
        LOG.debug("Loading hpo bulk")

        try:
            result = self.hpo_term_collection.insert_many(hpo_bulk)
        except (DuplicateKeyError, BulkWriteError) as err:
            raise IntegrityError(err)
        return result

    def hpo_term(self, hpo_id):
        """Fetch a hpo term

        Args:
            hpo_id(str)

        Returns:
            hpo_obj(dict)
        """
        LOG.debug("Fetching hpo term %s", hpo_id)

        return self.hpo_term_collection.find_one({"_id": hpo_id})

    def hpo_terms(self, query=None, hpo_term=None, text=None, limit=None):
        """Return all HPO terms

        If a query is sent hpo_terms will try to match with regex on term or
        description.

        Args:
            query(str): Part of a hpoterm or description
            hpo_term(str): Search for a specific hpo term
            limit(int): the number of desired results

        Returns:
            result(pymongo.Cursor): A cursor with hpo terms
        """
        query_dict = {}
        search_term = None
        if query:
            query_dict = {
                "$or": [
                    {"hpo_id": {"$regex": query, "$options": "i"}},
                    {"description": {"$regex": query, "$options": "i"}},
                ]
            }
            search_term = query
        elif text:
            new_string = ""
            for i, word in enumerate(text.split(" ")):
                if i == 0:
                    new_string += word
                else:
                    new_string += ' "{0}"'.format(word)
            LOG.info("Search HPO terms with %s", new_string)
            query_dict["$text"] = {"$search": new_string}
            search_term = text
        elif hpo_term:
            query_dict["hpo_id"] = hpo_term
            search_term = hpo_term

        limit = limit or int(10e10)
        res = (
            self.hpo_term_collection.find(query_dict)
            .limit(limit)
            .sort("hpo_number", pymongo.ASCENDING)
        )

        return res

    def generate_hpo_gene_list(self, *hpo_terms):
        """Generate a sorted list with namedtuples of hpogenes
        Each namedtuple of the list looks like (hgnc_id, count)
        Args:
            hpo_terms(iterable(str))
        Returns:
            hpo_genes(list(HpoGene))
        """
        genes = {}
        for term in hpo_terms:
            hpo_obj = self.hpo_term(term)
            if hpo_obj:
                for hgnc_id in hpo_obj["genes"]:
                    if hgnc_id in genes:
                        genes[hgnc_id] += 1
                    else:
                        genes[hgnc_id] = 1
            else:
                LOG.warning("Term %s could not be found", term)

        sorted_genes = sorted(genes.items(), key=operator.itemgetter(1), reverse=True)
        return sorted_genes

    def phenomodels(self, institute_id):
        """Return all phenopanels for a given institute
        Args:
            institute_id(str): institute id
        Returns:
            phenotype_models(pymongo.cursor.Cursor)
        """
        query = {"institute": institute_id}
        phenotype_models = self.phenomodel_collection.find(query)
        return phenotype_models

    def create_phenomodel(self, institute_id, name, description):
        """Create an empty advanced phenotype model with data provided by a user
        Args:
            institute_id(str): institute id
            name(str) a model name
            description(str) a model description
        Returns:
            phenomodel_obj(dict) a newly created model
        """
        phenomodel_obj = dict(
            institute=institute_id,
            name=name,
            description=description,
            submodels={},
            created=datetime.datetime.now(),
            updated=datetime.datetime.now(),
        )
        phenomodel_obj = self.phenomodel_collection.insert_one(phenomodel_obj)
        return phenomodel_obj

    def update_phenomodel(self, model_id, model_obj):
        """Update a phenotype model using its ObjectId
        Args:
            model_id(ObjectId): document ObjectId
            model_obj(dict): a dictionary of key/values to update a phenomodel with

        Returns:
            updated_model(dict): the phenomodel document after the update
        """
        updated_model = self.phenomodel_collection.find_one_and_update(
            {"_id": ObjectId(model_id)},
            {
                "$set": {
                    "name": model_obj["name"],
                    "description": model_obj["description"],
                    "submodels": model_obj.get("submodels", {}),
                    "updated": datetime.datetime.now(),
                }
            },
            return_document=pymongo.ReturnDocument.AFTER,
        )
        return updated_model

    def phenomodel(self, model_id):
        """Retrieve a phenomodel object using its ObjectId
        Args:
            model_id(ObjectId): document ObjectId
        Returns
            model_obj(dict)
        """
        query = {"_id": ObjectId(model_id)}
        model_obj = self.phenomodel_collection.find_one(query)
        return model_obj
