# coding: utf-8
from src.train_and_evaluate import *
from src.models import *
from src.equivalent import *
import time
import torch.optim
from src.expressions_transfer import *
import sys
import json
import os
import argparse
import pandas as pd

import warnings

def try_float(s):
    try:
        return float(s)
    except ValueError:
        print(f"Not a float {s}")
        return 0.0

def generate_csv(outputs,epoch):
    fieldnames = ['Id', 'Predicted']
    outputs_real = [try_float(s) for s in outputs]
    rows = {'Id': range(len(outputs_real)), 'Predicted': outputs_real}
    dataframe = pd.DataFrame(rows, columns=fieldnames)
    dataframe.to_csv('predicted-epoch-'+str(epoch)+'.csv', index=False)

warnings.simplefilter("ignore")

parser = argparse.ArgumentParser()

parser.add_argument('--model', default='fix', type=str, choices=['fix','ma-fix','reinforce','mapo'], help='training method')
parser.add_argument('--nstep', default=50, type=int, help='m-fix')
parser.add_argument('--name', default='fix', type=str, help='model name')
parser.add_argument('--number-of-problems', default='0', type=int, help='Number of training problems to use. 0 is all.')
parser.add_argument('--cross-validate', default=True, type=bool, help='Cross validate to test accuracy')
parser.add_argument('--batch_size', default=16, type=int, help='Batch size')


options = parser.parse_args()
model = options.model
n_step = options.nstep 
model_name = options.name
number_of_problems = options.number_of_problems
cross_validate = options.cross_validate

batch_size = options.batch_size
embedding_size = 128
hidden_size = 512
n_epochs = 100
learning_rate = 1e-3
weight_decay = 1e-5
beam_size = 5
n_layers = 2


data_train = load_raw_data("data/maths_train_pretty.json", True, number_of_problems)
data_test = load_raw_data("data/maths_test_pretty.json", False, number_of_problems)

if cross_validate:
    pairs_trained_whole = transfer_num(data_train)
    train_size = int(.9*len(pairs_trained_whole))
    test_size = int(.1*len(pairs_trained_whole))

    pairs_trained, pairs_tested = torch.utils.data.random_split(pairs_trained_whole, [train_size + (len(pairs_trained_whole) - train_size - test_size),test_size])
    print(f"KFold-Pairs Trained: {len(pairs_trained)}")
    print(f"KFold-Pairs Tested: {len(pairs_tested)}")
else:
    pairs_trained = transfer_num(data_train)
    pairs_tested = transfer_num(data_test)


fold = 1 #we can also iterate all the folds like GTS

input_lang, output_lang, train_pairs, test_pairs = prepare_data(pairs_trained, pairs_tested, 2)
# Initialize models
encoder = EncoderSeq(input_size=input_lang.n_words, embedding_size=embedding_size, hidden_size=hidden_size,
                        n_layers=n_layers)
predict = Prediction(hidden_size=hidden_size, op_nums=5,
                        input_size=2)
generate = GenerateNode(hidden_size=hidden_size, op_nums=5,
                        embedding_size=embedding_size)
merge = Merge(hidden_size=hidden_size, embedding_size=embedding_size)

# predict.load_state_dict(torch.load('pretrain/predict'))
# encoder.load_state_dict(torch.load('pretrain/encoder'))
# generate.load_state_dict(torch.load('pretrain/generate'))
# merge.load_state_dict(torch.load('pretrain/merge'))
# # the embedding layer is  only for generated number embeddings, operators, and paddings

encoder_optimizer = torch.optim.Adam(encoder.parameters(), lr=learning_rate, weight_decay=weight_decay)
predict_optimizer = torch.optim.Adam(predict.parameters(), lr=learning_rate, weight_decay=weight_decay)
generate_optimizer = torch.optim.Adam(generate.parameters(), lr=learning_rate, weight_decay=weight_decay)
merge_optimizer = torch.optim.Adam(merge.parameters(), lr=learning_rate, weight_decay=weight_decay)

encoder_scheduler = torch.optim.lr_scheduler.StepLR(encoder_optimizer, step_size=20, gamma=0.5)
predict_scheduler = torch.optim.lr_scheduler.StepLR(predict_optimizer, step_size=20, gamma=0.5)
generate_scheduler = torch.optim.lr_scheduler.StepLR(generate_optimizer, step_size=20, gamma=0.5)
merge_scheduler = torch.optim.lr_scheduler.StepLR(merge_optimizer, step_size=20, gamma=0.5)

# Move models to GPU
if USE_CUDA:
    print("Using CUDA")
    encoder.cuda()
    predict.cuda()
    generate.cuda()
    merge.cuda()

buffer_batches = [[] for i in range (len(train_pairs))]
buffer_batches_exp = [[] for i in range (len(train_pairs))]

stats = {
        'loss': [],
        'test_epoch': [],
        'test_result_acc3': [],
        'test_result_acc1': [],
        'test_result_acc5':[],
        'iteration': []
    }


iteration = 0
for epoch in range(n_epochs):
    encoder_scheduler.step()
    predict_scheduler.step()
    generate_scheduler.step()
    merge_scheduler.step()
    loss_total = 0
    input_batches, input_lengths, nums_batches, num_pos_batches, num_size_batches, num_ans_batches, num_id_batches = prepare_train_batch(train_pairs, batch_size)
    print("fold:", fold + 1)
    print("epoch:", epoch + 1)
    start = time.time()
    mask_flag = False
    pos = 0
    epo_iteration = 0
    for idx in range(len(input_lengths)): #batch

        if idx < 2 and epoch == 0:
            mask_flag = True
        buffer_batches_train = buffer_batches[pos : pos + len(input_lengths[idx])]
        buffer_batches_train_exp = buffer_batches_exp[pos : pos + len(input_lengths[idx])]
        loss, buffer_batch_new, iterations, buffer_batch_exp = train_tree(
            input_batches[idx], input_lengths[idx], 
            num_size_batches[idx], encoder, predict, generate, merge,
            encoder_optimizer, predict_optimizer, generate_optimizer, merge_optimizer, output_lang, num_pos_batches[idx], num_ans_batches[idx], nums_batches[idx], buffer_batches_train, buffer_batches_train_exp, epoch, input_lang, model, n_step, mask_flag)
        loss_total += loss
        iteration += iterations
        epo_iteration += iterations
        buffer_batches[pos : pos+len(input_lengths[idx])] = buffer_batch_new
        buffer_batches_exp[pos : pos+len(input_lengths[idx])] = buffer_batch_exp
        pos += len(input_lengths[idx])
    
    loss_total = loss_total if epo_iteration == 0 else loss_total/epo_iteration
    stats['loss'].append(loss_total)
    stats['iteration'].append(iteration)
    print("loss:", loss_total)
    print("training time", time_since(time.time() - start))
    print("--------------------------------")
    if epoch % 5 == 0 or epoch > n_epochs - 5:
        buffer_dict = {
        'id': [],
        'original_text': [],
        'segmented_text': [],
        'gt_equation': [],
        'ans':[],
        'gen_equations': []
        }

        value_ac3 = 0
        eval_total3 = 0
        value_ac1 = 0
        eval_total1 = 0
        value_ac5 = 0
        eval_total5 = 0
        start = time.time()
        outputs = []
        for k in range(len(test_pairs)):
            test_batch = test_pairs[k]
            test_exps = []
            output_sen = ""
            for widx in test_batch[0]:
                output_sen += input_lang.index2word[widx] + " "
            #print(f"test_batch {test_batch[5]}:  {output_sen}")

            test_results = evaluate_tree(test_batch[0], test_batch[1], encoder, predict, generate,
                                        merge, output_lang, test_batch[3], beam_size=beam_size)
            #print(test_results)
            #test_res = test_results[0]
            output = strip_string(test_results)
            outputs.append(output)

            for i in range (0, len(test_results)):
                test_res = test_results[i]
                val_ac, test_exp = compute_prefix_tree_result(test_res, test_batch[4], output_lang, test_batch[2])

                if val_ac:
                    test_exps.append(test_exp)
                if val_ac:
                    value_ac5 += 1
                eval_total5 += 1

                if i < 3:
                    if val_ac:
                        value_ac3 += 1
                    eval_total3 += 1

                if i == 0:
                    if val_ac:
                        value_ac1 += 1
                    eval_total1 += 1

            # id2 = int(test_pairs[k][7])
            # buffer_dict['id'].append(id2)
            # id2 = id2 - 1
            # buffer_dict['original_text'].append(data[id2]['original_text'])
            # buffer_dict['segmented_text'].append(data[id2]['segmented_text'])
            # buffer_dict['ans'].append(data[id2]['ans'])
            # buffer_dict['gt_equation'].append(data[id2]['equation'])
            # buffer_dict['gen_equations'].append(test_exps)
        generate_csv(outputs,epoch)
        stats['test_epoch'].append (epoch)
        stats['test_result_acc3'].append(float(value_ac3) / eval_total3)
        stats['test_result_acc1'].append(float(value_ac1) / eval_total1)
        stats['test_result_acc5'].append(float(value_ac5) / eval_total5)

        print(value_ac1, eval_total1)
        print("test_answer_acc5", float(value_ac5) / eval_total5)
        print("test_answer_acc3", float(value_ac3) / eval_total3)
        print("test_answer_acc1", float(value_ac1) / eval_total1)
        print("testing time", time_since(time.time() - start))
        print("------------------------------------------------------")
        torch.save(encoder.state_dict(), "models/encoder")
        torch.save(predict.state_dict(), "models/predict")
        torch.save(generate.state_dict(), "models/generate")
        torch.save(merge.state_dict(), "models/merge")


