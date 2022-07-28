"""
Directory structure -
    src/
    -- /
    data/
    -- dataset_csv
    -- label_titles_csv
    -- overlap_scores/
        -- [overlap_11101700_12141700.csv, # overlap_classA_classB
            ...
            ]
    -- label_frequency_csv
    -- unspsc_title_similarity_csv
"""

import logging
import os
import re

import pandas as pd
import spacy

from pandarallel import pandarallel
from spacy_langdetect import LanguageDetector

from tqdm import tqdm



class OverlapAnalysis:

    '''
    Member variables as follows.
    dataset_df: input dataset.
    label_frequency_df: unique UNSPSC labels along with their titles and frequency.
    unspsc_title_similarity_df: pairs of UNSPSC titles and their semantic similarity.

    Note: dataset_df is the only input; dataset that will have to be supplied to this code containing LIDs and UNSPSC labels; every other dataframe is generated by this code.
    '''

    DATASET_PATH = ''
    LABEL_FREQUENCY_PATH = ''
    UNSPSC_TITLE_SIMILARITY_PATH = ''
    LABEL_TITLES_PATH = ''
    OVERLAP_SCORES_DIR = ''
    OA_RESULT_PATH = ''

    LOGGING_FORMATTER = ''
    DATE_FORMATTER = ''
    logger = None

    dataset_df = pd.DataFrame()

    label_titles_df = pd.DataFrame()

    title_dfs = {
        'v23_1': pd.DataFrame(),
        'v23_2': pd.DataFrame(),
        'v23_3': pd.DataFrame()
    }

    label_frequency_df = pd.DataFrame(
        columns = [
            'label',
            'label_title',
            'frequency', # optional
            'level' # optional
        ]
    )

    unspsc_title_similarity_df = pd.DataFrame(
        columns = [
            'label_1',
            'label_2',
            'label_1_title',
            'label_2_title',
            'similarity'
        ]
    )

    cross_product_df = pd.DataFrame(
        columns = [
            'lid_1',
            'lid_2',
            'score'
        ]
    )

    similarity_metrics = [
        'unigram_overlap_score'
    ]

    spacy_nlp = None


    def __init__(
        self,
        oa_dir_path: str = '../Data/OA',
        dataset_path: str = 'train_data_initial_invoice_sample.csv',
        label_frequency_path: str = 'label_frequency.csv',
        unspsc_title_similarity_path: str = 'unspsc_title_similarity.csv',
        label_titles_path: str = 'UNSPSC Comparison v905 vs v23.xlsx',
        overlap_scores_dir: str = 'overlap_scores',
        oa_result_path: str = 'oa_results.csv',
        title_sheets: list = ['v23_1', 'v23_2', 'v23_3']
    ):

        '''
        Constructor that takes in root path of data directory within which the input dataset exists.
        Necessary folders will be generated within this directory itself and populated with intermediate and final CSVs.

        dataset_csv_name: filename of the input CSV file relative to the data directory.
        '''

        self.DATASET_PATH = os.path.join(oa_dir_path, dataset_path)
        self.LABEL_FREQUENCY_PATH = os.path.join(oa_dir_path, label_frequency_path)
        self.UNSPSC_TITLE_SIMILARITY_PATH = os.path.join(oa_dir_path, unspsc_title_similarity_path)
        self.LABEL_TITLES_PATH = os.path.join(oa_dir_path, label_titles_path)
        self.OA_RESULT_PATH = os.path.join(oa_dir_path, oa_result_path)
        self.OVERLAP_SCORES_DIR = os.path.join(oa_dir_path, overlap_scores_dir)

        self.dataset_df = pd.read_csv(self.DATASET_PATH)

        for sheet in title_sheets:
            self.title_dfs[sheet] = pd.read_excel(self.LABEL_TITLES_PATH, engine = 'openpyxl', sheet_name = sheet)

        tqdm.pandas()

        pandarallel.initialize()

        self.spacy_nlp = spacy.load('en_core_web_sm')
        self.spacy_nlp.add_pipe(
            LanguageDetector(),
            name = 'language_detector',
            last = True
        )

        """ self.LOGGING_FORMATTER = '%(asctime)s.%(msecs)03d - %(threadName)s - %(levelname)s - %(message)s'
        self.DATE_FORMATTER = '%Y-%m-%d %H:%M:%S'
        logging.basicConfig(format = self.LOGGING_FORMATTER, datefmt = self.DATE_FORMATTER, level = print)
        self.logger = logging.getLogger(__name__) """

        # unigram_overlap_scores, lcs_score, levenshtein_score, cosine_similarity_score, spacy_similarity_score
        """ self.unspsc_title_similarity_df['unigram_overlap_scores'], \
        self.unspsc_title_similarity_df['lcs_score'] \
        self.unspsc_title_similarity_df['levenshtein_score'] \
        ...
            = self.run_overlap_analysis() """



    def get_unspsc_label_title(self, unspsc_code: int) -> str: # train_data_initial_invoice

        '''
        Takes in 8-digit UNSPSC code (str or numeric type), refers to external CSV and returns label title if found.
        Returns 'Unknown' if invalid UNSPSC code is passed in or external CSV does not have a match for a semantically valid code.
        '''

        '''
        Calls: None.
        Callee(s): generate_label_frequency().
        '''

        title = 'Unknown'

        for source_df in self.title_dfs:
            source_df = self.title_dfs[source_df]
            if len(source_df[source_df.Code == unspsc_code].Title):
                title = source_df[source_df.Code == unspsc_code].Title.values[0]
                
        return title



    def generate_label_frequency(self) -> pd.DataFrame: # train_data_initial_invoice

        '''
        Iterates through unique UNSPSC codes from self.dataset_df, ordered by frequency, populates labels with their label title into a self.label_frequency_df.
        Also generates a CSV file.
        Possible improvement: maintain a permanent CSV file which records ell UNSPSC labels (and their titles ever encountered) - possibly better done with a database.
        '''

        '''
        Calls: get_unspsc_label_title().
        Callee(s): constructor.
        '''

        if os.path.isfile(self.LABEL_FREQUENCY_PATH):
            print("label frequency file found.")
            return pd.read_csv(self.LABEL_FREQUENCY_PATH)

        print("label frequency file not found. generating.")

        df_v23_levels = self.dataset_df.v23_level3.value_counts()

        rows = []

        for code in df_v23_levels.keys():
            unspsc_title = self.get_unspsc_label_title(code)
            
            # determining level. (1 * (level[0] % 2 == 1) is added to handle the corner cases like 94132001.
            level = [m.start() for m in re.finditer(r'(?=(00))', str(code))]
            level = 4 - len(level) + (level[0] % 2 == 1 if len(level) == 1 else len(level) // 2)
            
            rows.append([code, level, df_v23_levels[code], unspsc_title])
            
        self.label_frequency_df = pd.DataFrame(data = rows,
                                    columns=['label', 'level', 'count', 'label_title'])

        self.label_frequency_df = self.label_frequency_df[self.label_frequency_df.label_title != 'Unknown']

        self.label_frequency_df.to_csv(self.LABEL_FREQUENCY_PATH)

        print("label frequency file generated and saved as CSVfile to: " + self.LABEL_FREQUENCY_PATH)

        return self.label_frequency_df



    def unigrams_in_common(
        self,
        lid_1: str,
        lid_2: str
    ) -> [float, list]:

        '''
        Custom method that returns a similarity score between two preprocessed LIDs.
        '''

        unigrams_1 = list(set(lid_1.split(' ')))
        unigrams_2 = list(set(lid_2.split(' ')))

        common_unigrams = list(set(unigrams_1).intersection(unigrams_2))

        return len(common_unigrams) / ((len(unigrams_1) + len(unigrams_2)) / 2), ','.join(common_unigrams)



    def compute_similarity(
        lid_1: str,
        lid_2: str,
        similarity_metric: str = 'spacy'
    ) -> float: # overlap_analysis

        '''
        Takes in pair of strings and uses a predefined method to calculate similarity.
        '''

        '''
        Calls: get_spacy_similarity().
        Callee(s): generate_interest_pairs(), run_overlap_analysis().
        '''

        if similarity_metric == 'spacy':

            return self.get_spacy_similarity(lid_1, lid_2)



    def generate_interest_pairs(self, similarity_metric: str = 'spacy') -> pd.DataFrame:

        '''
        Uses self.label_frequency_df to list all possible pairs of classes and computes similarity between them to populate self.unspsc_title_similarity_df.
        '''

        '''
        Calls: compute_similarity().
        Callee(s): constructor.
        '''


        def get_spacy_similarity(lid_1: str, lid_2: str) -> float:

            '''
            Uses spacy's builtin similarity scores.
            '''

            return self.spacy_nlp(lid_1).similarity(self.spacy_nlp(lid_2))
        


        if os.path.isfile(self.UNSPSC_TITLE_SIMILARITY_PATH):
            print("label similarity file found.")
            return pd.read_csv(self.UNSPSC_TITLE_SIMILARITY_PATH)

        print("label similarity file not found. generating.")

        index = pd.MultiIndex.from_product([self.label_frequency_df.label, self.label_frequency_df.label], names = ["label_1", "label_2"])
        crossed_labels = pd.DataFrame(index = index).reset_index()

        index = pd.MultiIndex.from_product([self.label_frequency_df.label_title, self.label_frequency_df.label_title], names = ["label_title_1", "label_title_2"])
        crossed_titles = pd.DataFrame(index = index).reset_index()

        unspsc_title_similarity_df = pd.concat([crossed_labels, crossed_titles], axis = 1)
        unspsc_title_similarity_df = unspsc_title_similarity_df[unspsc_title_similarity_df.label_1 != unspsc_title_similarity_df.label_2]
        
        # drop (b, a) values when (a, b) already exist
        # unspsc_title_similarity_df = unspsc_title_similarity_df.sort_values('label_1')
        unspsc_title_similarity_df = unspsc_title_similarity_df[unspsc_title_similarity_df['label_1'] < unspsc_title_similarity_df['label_2']]

        unspsc_title_similarity_df['titles_similarity_score'] = unspsc_title_similarity_df[['label_title_1', 'label_title_2']].parallel_apply(lambda x: get_spacy_similarity(*x), axis = 1)

        self.unspsc_title_similarity_df = unspsc_title_similarity_df

        self.unspsc_title_similarity_df.to_csv(self.UNSPSC_TITLE_SIMILARITY_PATH)

        print("label similarity file generated and saved as CSVfile to: " + self.UNSPSC_TITLE_SIMILARITY_PATH)

        return self.unspsc_title_similarity_df



    def remove_special_chars(self, lid_string: str, specials: str = ',.-') -> str:

        '''
        Replaces parameterized (a specified list of) special characters in a string with a single whitespace.
        '''

        '''
        Calls: None.
        Callee(s): reduce_by_unigrams().
        '''

        for special in specials:
            lid_string = lid_string.replace(special, ' ')

        return lid_string



    def reduce_by_unigrams(
        self,
        lid_string: str # list of LID strings: PartDescription1, PartDescription, InvoiceDescription, PODescription
    ) -> str: # print_uni, unigramsInCommon, oa_2; sampling_6.4m

        '''
        Splits a string by a list of provided special characters, then reduces strings to unique unigrams.
        '''

        '''
        Calls: remove_special_chars().
        Callee(s): preprocess_lids().
        '''

        if isinstance(lid_string, float):
            return ''
        
        unigrams = []

        lid_string = self.remove_special_chars(lid_string)
        for word in lid_string.split():
            if word not in unigrams:
                unigrams.append(word)

        return ' '.join(unigrams)



    def preprocess_lids(self) -> None: # oa_2; sampling_6.4m

        '''
        Add two columns to self.dataset_df; one that uses simple concatenation of all line item descriptions
        and another that uses special sanitization to reduce string to only common unigrams.
        '''

        '''
        Calls: reduce_by_unigrams().
        Callee(s): constructor.
        '''

        print("preprocessing LIDs into concatenated and reduced.")

        self.dataset_df['PartDescription1'] = self.dataset_df['PartDescription1'].fillna('')
        self.dataset_df['PartDescription2'] = self.dataset_df['PartDescription2'].fillna('')
        self.dataset_df['InvoiceDescription'] = self.dataset_df['InvoiceDescription'].fillna('')
        self.dataset_df['PODescription'] = self.dataset_df['PODescription'].fillna('')
        self.dataset_df['lid_concatenated'] = self.dataset_df['PartDescription1'] + self.dataset_df['PartDescription2'] + self.dataset_df['InvoiceDescription'] + self.dataset_df['PODescription']
        self.dataset_df['lid_reduced'] = self.dataset_df['lid_concatenated'].apply(self.reduce_by_unigrams)

        print("done preprocessing LIDs.")



    def overlap_analysis(self, offset: int = 0) -> int: # oa_2

        '''
        Iterates through pairs of classes from self.unspsc_title_similarity_df,
        and returns a global averaged overlap score, which is appended in different columns on self.unspsc_title_similarity_df.
        '''

        def compute_class_overlaps(label_1: int, label_2: int) -> None:

            '''
            Computes each type of similarity score for a `pair` of classes as specified in self.similarity_metrics, and returns a dictionary of said score.
            Also, exports these results to a CSV file for each pair of LID (i, j) where i is from Class A and j is from Class B.
            '''

            csv_name = 'overlap_' + str(label_1) + '_' + str(label_2) + '.csv'

            if not os.path.exists(self.OVERLAP_SCORES_DIR):
                os.makedirs(self.OVERLAP_SCORES_DIR)

            if os.path.isfile(os.path.join(self.OVERLAP_SCORES_DIR, csv_name)):
                
                """ print(csv_name + ' already found.') """
                crossed_lid_dfs = pd.read_csv(os.path.join(self.OVERLAP_SCORES_DIR, csv_name))
                return sum(crossed_lid_dfs.unigram_overlap_score) / len(crossed_lid_dfs.unigram_overlap_score)
            
            """ print('comparing: ' + str(label_1) + ':' + str(label_2)) """

            df1 = self.dataset_df[self.dataset_df.v23_level3 == label_1]
            df2 = self.dataset_df[self.dataset_df.v23_level3 == label_2]

            # perform cross product on LIDs to generate all possible pairs.
            index = pd.MultiIndex.from_product([df1.lid_reduced, df2.lid_reduced], names = ["lid_1_reduced", "lid_2_reduced"])
            crossed_lid_dfs = pd.DataFrame(index = index).reset_index()
            
            # drop (b, a) values when (a, b) already exist
            # crossed_lid_dfs = crossed_lid_dfs.sort_values('lid_1_reduced')
            # crossed_lid_dfs = crossed_lid_dfs[crossed_lid_dfs['lid_1_reduced'] < crossed_lid_dfs['lid_2_reduced']]

            # get scores and commons comma separated unigrams
            crossed_lid_dfs['unigram_overlap_score'], crossed_lid_dfs['common_unigrams'] = zip(*crossed_lid_dfs[['lid_1_reduced', 'lid_2_reduced']].parallel_apply(lambda x: self.unigrams_in_common(*x), axis = 1).to_numpy())

            crossed_lid_dfs.unigram_overlap_score = crossed_lid_dfs.unigram_overlap_score * 100
            
            # keep count of duplicate rows and drop duplicates before exporting to CSV
            crossed_lid_dfs['count'] = crossed_lid_dfs.groupby(['lid_1_reduced', 'lid_2_reduced']).transform('count')['unigram_overlap_score']
            crossed_lid_dfs.drop_duplicates().sort_values('unigram_overlap_score', ascending = False).to_csv(os.path.join(self.OVERLAP_SCORES_DIR, csv_name))

            return sum(crossed_lid_dfs.unigram_overlap_score) / len(crossed_lid_dfs.unigram_overlap_score)

            '''
            Calls: compute_similarity(), remove_special_chars().
            Callee(s): run_overlap_analysis().
            '''

        print('beginning overlap analysis.')

        self.unspsc_title_similarity_df['similarity'] = self.unspsc_title_similarity_df[['label_1', 'label_2']].progress_apply(lambda x: compute_class_overlaps(*x), axis = 1)
        self.unspsc_title_similarity_df.to_csv(self.OA_RESULT_PATH)

        print('overlap analysis concluded. result CSVfile saved to: ' + self.OA_RESULT_PATH)

        '''
        Calls: compute_class_overlaps().
        Callee(s): constructor.
        '''



    def run_overlap_analysis(self):

        self.label_frequency_df = self.generate_label_frequency()
        self.unspsc_title_similarity_df = self.generate_interest_pairs()
        self.preprocess_lids()
        self.overlap_analysis()