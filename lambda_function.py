
import boto3
import logging
from datetime import datetime
from datetime import timedelta
import json
import uuid
import os

# setup simple logging for INFO
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.setLevel(logging.ERROR)

# define the connection
ec2 = boto3.resource('ec2')
cw = boto3.client('cloudwatch')
s3 = boto3.resource('s3')
s3client = boto3.client('s3')
ec2_client = boto3.client('ec2')


def lambda_handler(event, context):
 try:    
    # Use the filter() method of the instances collection to retrieve
    # all running EC2 instances.

    filters = [{
        'Name': 'instance-state-name',
        'Values': ['running']
    }
    ]

    # filter the instances
    instances = ec2.instances.filter(Filters=filters)
    bucketname = os.getenv('S3_BUCKET')

    # locate all running instances
    RunningInstances = [instance.id for instance in instances]

    dnow = datetime.now()


    for instance in instances:
        for tags in instance.tags:
            if tags["Key"] == 'Name':

                ec2_instance_id = instance.id
                
                metrics_list_response = cw.list_metrics(
                Dimensions=[{'Name': 'InstanceId', 'Value': ec2_instance_id}])
            
                metrics_response = get_metrics(metrics_list_response, cw)
                metrics_response["DEVICE"] = ec2_instance_id
                instanceData = json.dumps(metrics_response, default=datetime_handler)
                print(metrics_response)
                bucket_name = bucketname
                filename = str(uuid.uuid4())+ "__"+ec2_instance_id +'_InstanceMetrics.json'
                key = ec2_instance_id + "/" + filename
                s3client.put_object(Bucket=bucket_name, Key=key, Body=instanceData)
                
 except Exception as e:
        logger.exception("Error while getting EC2 cloudwatch metrics {0}".format(e))                

            



def datetime_handler(x):
    if isinstance(x, datetime):
        return x.isoformat()
    raise TypeError("Unknown type")

def get_metrics(metrics_list_response, cw):
    """
    This method will retrieve the metrics from cloudwatch.
    It will iterate through the list of metrics available and form the metrics query
    """
    metric_data_queries = []
    metrices = metrics_list_response.get('Metrics')
    for metrics in metrices:
        namespace = metrics.get("Namespace")
        dimensions = metrics.get("Dimensions")
        metric_name = metrics.get("MetricName")
        metric_id = metric_name
        if metric_name == 'DiskSpaceUtilization':
            for dimension in dimensions:
                dimension_name = dimension.get("Name")
                if dimension_name == "Filesystem":
                    """ If metric is for disk, note the file system """
                    file_system = dimension.get("Value")
                    metric_id = metric_name + file_system.replace("/", "_")
                    break

        metrics_data_query = {"Id": metric_id.lower(), "MetricStat": {
            "Metric": {"Namespace": namespace,
                       "MetricName": metric_name,
                       "Dimensions": dimensions},
            "Period": 300,
            "Stat": "Average"
        }, "Label": metric_name + "Response", "ReturnData": True}
        metric_data_queries.append(metrics_data_query)

    metrics_response = cw.get_metric_data(
        MetricDataQueries=metric_data_queries,
        StartTime=datetime.now()+timedelta(minutes=-5),
        EndTime=datetime.now()
    )

    return metrics_response
