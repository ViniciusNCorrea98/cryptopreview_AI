import random
import numpy as np
import pandas as pd
import os
import sklearn
from sklearn import preprocessing
from collections import deque
import time
import tensorflow as tf
from tensorflow import keras
from keras.models import Sequential
from keras.layers import Dense, Dropout, LSTM,BatchNormalization
from keras.callbacks import TensorBoard
from keras.callbacks import ModelCheckpoint
import keras.optimizers.legacy as legacy_optimizers



SEQ_LEN = 60
FUTURE_PERIOD_PREDICT = 3
RATIO_TO_PREDICT = "LTC-USD"
EPOCHS = 5
BATCH_SIZE = 32
NAME = f"{SEQ_LEN}-SEQ-{FUTURE_PERIOD_PREDICT}-PRED-{int(time.time())}"

def classify (current, future):
    if float(future) > float(current):
        return 1
    else:
        return 0

def preprocess_df(df):
    df = df.drop("future", axis=1)

    for col in df.columns:
        if col != 'target':
            df[col] = df[col].pct_change()
            df.dropna(inplace=True)
            df[col] = sklearn.preprocessing.scale(df[col].values)
    df.dropna(inplace=True)

    sequential_data = []
    prev_days = deque(maxlen = SEQ_LEN)

    for i in df.values:
        prev_days.append([n for n in i[:1]])
        if len(prev_days) == SEQ_LEN:
            sequential_data.append([np.array(prev_days), i[-1]])

    random.shuffle(sequential_data)

    buys=[]
    sells=[]

    for seq, target, in sequential_data:
        if target==0:
            sells.append([seq, target])
        elif target==1:
            buys.append(([seq, target]))

    random.shuffle(buys)
    random.shuffle(sells)

    lower = min(len(buys), len(sells))
    buys = buys[:lower]
    sells = sells[:lower]

    sequential_data = buys+sells
    random.shuffle(sequential_data)

    X=[]
    y=[]

    for seq, target in sequential_data:
        X.append(seq)
        y.append(target)

    return np.array(X), y



#df = pd.read_csv("crypto_data/LTC-USD.csv", names=["time", "low", "high", "open", "close", "volume"])

main_df = pd.DataFrame()

ratios = ['BTC-USD', "LTC-USD", "ETH-USD", "BCH-USD"]

for ratio in ratios:
    ratio = ratio.split('.csv')[0]
    dataset=f"crypto_data/{ratio}.csv"

    df = pd.read_csv(dataset,  names=["time", "low", "high", "open", "close", "volume"])
    print(df.head())

    df.rename(columns={"close": f"{ratio}_close", "volume": f"{ratio}_volume"}, inplace=True)

    df.set_index("time", inplace=True)

    df = df[[f"{ratio}_close", f"{ratio}_volume"]]

    if len(main_df) ==0:
        main_df = df
    else:
        main_df = main_df.join(df)

main_df.ffill(inplace=True)
main_df.dropna(inplace=True)

main_df['future'] = main_df[f'{RATIO_TO_PREDICT}_close'].shift(-FUTURE_PERIOD_PREDICT)

main_df['target'] = list(map(classify, main_df[f'{RATIO_TO_PREDICT}_close'], main_df['future']))


#print(main_df[[f'{RATIO_TO_PREDICT}_close', 'future', 'target']].head(10))

times = sorted(main_df.index.values)
last_5pct = times[-int(0.05*len(times))]

validation_main_df = main_df[(main_df.index >= last_5pct)]
main_df=main_df[(main_df.index < last_5pct)]

train_x, train_y = preprocess_df(main_df)
validation_x, validation_y = preprocess_df(validation_main_df)

print(f"train data: {len(train_x)} validation: {len(validation_x)}")
print(f"Dont buy: {train_y.count(0)}, buys: {train_y.count(1)}")
print(f"VALIDATION Dont buys: {validation_y.count(0)}, buys: {validation_y.count(1)}")

validation_y = np.array(validation_y)


model = Sequential()
model.add(LSTM(128, input_shape=(train_x.shape[1:]), return_sequences=True))
model.add(Dropout(0.2))
model.add(BatchNormalization())

model.add(LSTM(128, return_sequences=True))
model.add(Dropout(0.1))
model.add(BatchNormalization())

model.add(LSTM(128))
model.add(Dropout(0.2))
model.add(BatchNormalization())

model.add(Dense(32, activation='relu'))
model.add(Dropout(0.2))

#Because we have two outputs => buy and sell
model.add(Dense(2, activation='softmax'))

opt = keras.optimizers.SGD(learning_rate=0.001)

model.compile(
    loss='sparse_categorical_crossentropy',
    optimizer=opt,
    metrics=['accuracy']
)

#Let's call TesnorBoard callback:
tensorboard = TensorBoard(log_dir="logs/{}".format(NAME))

filepath = "models/RNN_Final-{epoch:02d}-{val_accuracy:.3f}.model"

checkpoint = ModelCheckpoint(filepath, monitor='val_accuracy', verbose=1, save_best_only=True, mode='max')

print(type(train_x))
print(type(train_y))

train_x= np.array(train_x)
train_y=np.array(train_y)

train_y_copy = np.copy(train_y)



#Training the model...
history = model.fit(train_x, train_y_copy,  batch_size=BATCH_SIZE, epochs=EPOCHS, validation_data=(validation_x, validation_y), callbacks=[tensorboard, checkpoint])
#Running model preformance

score = model.evaluate(validation_x, validation_y, verbose=0)
print('Test loss: ', score[0])
print('Test accuracy:', score[1])

model.save("models/{}".format(NAME))










